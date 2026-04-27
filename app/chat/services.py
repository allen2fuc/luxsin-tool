



import asyncio
import logging
import uuid
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
import json
# from typing import Protocol

from app.chat.constants import MessageRole, MessageRole
from app.core.anthropic import anthropic_client
from app.core.config import settings
from app.core.database import get_db_cm
from app.core.redis import redis_client
from app.luxsin.constants import LANGUAGE_NAME

from .constants import AI_SUMMARY_TEXT_PROMPT, AI_SYSTEM_PROMPT, BACKEND_TOOLS, FRONTEND_TOOLS, GENERATE_TITLE_PROMPT
from . import crud as chat_crud
from .models import DEFAULT_TITLE, Chat, Message
from .schemas import MessagePayload, QuestionRequest, ToolResult
from .constants import MessageType, MessageRole

logger = logging.getLogger(__name__)


class Result(BaseModel):
    ok: bool
    content: str | None = None
    message: str | None = None

class BackendToolRequest(BaseModel):
    """后端工具入参；不要放入 AsyncSession，否则 Pydantic 无法生成 schema。"""

    chat_id: uuid.UUID
    fn_id: str
    fn_name: str
    fn_input: dict
    messages: list
    question: QuestionRequest

# class BackendTool(Protocol):
#     async def __call__(self, request:BackendToolRequest) -> Result:
#         ...


def extract_text_context(messages: list[MessagePayload], limit: int = 6) -> list[MessagePayload]:
    """
    过滤工具调用相关内容，仅保留用户与助手的文本上下文。
    """
    cleaned_messages: list[MessagePayload] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role not in (MessageRole.USER, MessageRole.ASSISTANT):
            continue

        if isinstance(content, str):
            text = content.strip()
            if text:
                cleaned_messages.append(MessagePayload(role=role, content=text))
            continue

        if isinstance(content, list):
            text_blocks: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text", "")).strip()
                    if text:
                        text_blocks.append(text)
            if text_blocks:
                cleaned_messages.append(
                    MessagePayload(role=role, content="\n".join(text_blocks))
                )

    return cleaned_messages[-limit:] if limit > 0 else cleaned_messages


# 优化EQ的后端工具
# class OptimizeEqBackendTool:
#     async def __call__(self, request:BackendToolRequest) -> Result:
#         user_input_message = (
#             "Input context for EQ optimization:\n"
#             f"{json.dumps(request.tool_input, indent=2, ensure_ascii=False)}\n\n"
#             "Please generate an optimized PEQ JSON."
#         )

#         # 控制上下文长度，减少噪音和 token 消耗
#         new_messages = extract_text_context(request.messages, limit=6)
#         new_messages.append(MessagePayload(role=MessageRole.USER, content=user_input_message))

#         print_messages(new_messages)

#         try:

#             resp = await anthropic_client.messages.create(
#                 system=[
#                     {"type": "text", "text": AI_EQ_OPTIMIZE_PROMPT, "cache_control": {"type": "ephemeral"}},
#                 ],
#                 model=settings.AI_MODEL,
#                 messages=new_messages,
#                 max_tokens=settings.OPTIMIZE_EQ_MAX_TOKENS,
#                 output_config={
#                     "format": {
#                         "type": "json_schema",
#                         "schema": {
#                             "type": "object",
#                             "properties": {
#                                 "name": {"type": "string"},
#                                 "brand": {"type": "string"},
#                                 "model": {"type": "string"},
#                                 "filters": {
#                                     "type": "array",
#                                     "items": {
#                                         "type": "object",
#                                         "properties": {
#                                             "type": {"type": "integer", "enum": [0, 1, 2, 3, 4, 5, 6, 7]},
#                                             "fc": {"type": "number", "minimum": 1, "maximum": 20000},
#                                             "gain": {"type": "number", "minimum": -15, "maximum": 15},
#                                             "q": {"type": "number", "minimum": 0.1, "maximum": 10},
#                                         },
#                                         "required": ["type", "fc", "gain", "q"],
#                                         "additionalProperties": False,
#                                     },
#                                     "maxItems": 10,
#                                 },
#                                 "preamp": {"type": "number"},
#                                 "canDel": {"type": "number", "enum": [0, 1]},
#                                 "autoPre": {"type": "number", "enum": [0, 1]},
#                             },
#                             "required": ["name", "brand", "model", "filters", "preamp", "canDel", "autoPre"],
#                             "additionalProperties": False,
#                         },
#                     }
#                 },
#             )

#             result = resp.content[0].text if resp.content else "{}"
#             optimized_peq = json.loads(result) if result else {}

#             db_messages = [
#                 Message(chat_id=request.chat_id, role="user", content=user_input_message, tokens=resp.usage.input_tokens, type=MessageType.OPTIMIZING),
#                 Message(chat_id=request.chat_id, role="assistant", content=result, tokens=resp.usage.output_tokens, type=MessageType.OPTIMIZING, before_peq=tool_input, after_peq=optimized_peq),
#             ]

#             await chat_crud.create_message_batch(db_messages, request.db)

#             return Result(ok=True, content=result)
#         except Exception as e:
#             logger.exception(e)
#             return Result(ok=False, message="Tool execution failed, error reason: " + str(e))


# BACKEND_TOOLS_MAP = {
#     "optimize_eq": OptimizeEqBackendTool(),
# }

def _format_tool_use(block) -> dict:
    return {
        "type": "tool_use",
        "id": getattr(block, "id"),
        "name": getattr(block, "name"),
        "input": getattr(block, "input"),
    }

def _format_text(block) -> dict:
    return {
        "type": "text",
        "text": getattr(block, "text"),
    }

CONTENT_FORMATTERS = {
    "tool_use": _format_tool_use,
    "text": _format_text,
}

async def execute_backend_tool(request: BackendToolRequest) -> ToolResult:
    if request.fn_name in BACKEND_TOOLS_FUNC:
        result: str = BACKEND_TOOLS_FUNC[request.fn_name](request.question)
        return ToolResult(tool_use_id=request.fn_id, content=result)
    return ToolResult(tool_use_id=request.fn_id, content="Tool not found", is_error=True)

async def execute_frontend_tool(result_id:str) -> dict:
    result = await wait_for_frontend_result(result_id, timeout=settings.WAIT_FOR_FRONTEND_RESULT_TIMEOUT)
    logger.info(f"Frontend tool result: {result}")
    return result

async def wait_for_frontend_result(tool_use_id: str, timeout: int) -> dict:
    channel = f"tool_result:{tool_use_id}"
    
    async def _wait() -> dict:
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            try:
                existing = await redis_client.get(channel)
                if existing:
                    return json.loads(existing)
                
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        result = await redis_client.get(channel)
                        if result:
                            return json.loads(result)
            finally:
                await pubsub.unsubscribe(channel)
                await redis_client.delete(channel)
    
    try:
        return await asyncio.wait_for(_wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": "Access to tool execution timed out.", "is_error": True}



def get_system_prompt(question: QuestionRequest) -> str:
    return AI_SYSTEM_PROMPT.substitute( 
        device=question.device_setting.device
    )


async def generate_title(chat_id: uuid.UUID, messages: list) -> None:
    try:
        generate_title_prompt = GENERATE_TITLE_PROMPT

        # 用户输入的信息，将用户输入的消息合并（content 可能是 list/dict，需要先转字符串）
        merged_user_contents = []
        for msg in messages:
            if msg.get("role") != MessageRole.USER:
                continue
            c = msg.get("content", "")
            if isinstance(c, str):
                merged_user_contents.append(c)
            
        user_input_message = "User input messages:\n" + "\n".join(merged_user_contents)
        user_message = [MessagePayload(role=MessageRole.USER, content=user_input_message)]

        resp = await anthropic_client.messages.create(
            system=[
                {"type": "text", "text": generate_title_prompt, "cache_control": {"type": "ephemeral"}},
            ],
            model=settings.AI_MODEL,
            messages=user_message,
            max_tokens=10,
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "string",
                        "maxLength": 10,
                    },
                },
            },
        )

        result = resp.content[0].text if resp.content else ""
        replaced_result = result.strip().strip('"') if result else DEFAULT_TITLE
        usage = resp.usage

        logger.info(f"generate title: {chat_id} {result}")

        async with get_db_cm() as db:

            if replaced_result != DEFAULT_TITLE and DEFAULT_TITLE not in replaced_result:
                await chat_crud.update_chat_title(chat_id, replaced_result, db)

            await save_message(chat_id, MessageRole.USER, user_input_message, db, type=MessageType.OPTIMIZING, tokens=usage.input_tokens)
            await save_message(chat_id, MessageRole.ASSISTANT, result, db, type=MessageType.OPTIMIZING, tokens=usage.output_tokens)
            return None

    except Exception as e:
        logger.exception(e)
    


async def publish_tool_result(tool_use_id: str, content: dict):
    channel = f"tool_result:{tool_use_id}"
    await redis_client.set(channel, json.dumps(content, ensure_ascii=False), ex=settings.CACHE_TOOL_RESULT_TIMEOUT)
    await redis_client.publish(channel, "ready")

def repair_messages(messages: list) -> list:
    """
    修复 messages 中的数据丢失或中断。
    1. assistant 消息含 tool_use，检查下一条是否有对应 tool_result, 如果缺失则补齐。
    2. 连续相同 role，合并内容
    3. 返回修复后的 messages
    """

    new_messages = []
    i = 0
    length = len(messages)

    while i < length:
        msg = messages[i]
        role = msg["role"]
        content = msg["content"]

        # 如果是AI没有回复
        if role == MessageRole.USER.value:
            next_msg = messages[i + 1] if i + 1 < length else None
            if next_msg and next_msg["role"] != MessageRole.ASSISTANT.value:
                new_messages.append(msg)
                new_messages.append(MessagePayload(role=MessageRole.ASSISTANT, content= "( Lost reply, please continue )"))
                i += 1
                continue

        # 如果是Tool请求，没有Tool结果
        if role == MessageRole.ASSISTANT.value:
            content_list = content if isinstance(content, list) else []
            tool_use_ids = {b["id"] for b in content_list if b.get("type") == "tool_use"}
            # 如果是Tool调用，检查下一条是否有对应 tool_result
            if tool_use_ids:
                next_msg = messages[i + 1] if i + 1 < length else None
                if next_msg and next_msg["role"] == MessageRole.USER.value:
                    next_content = next_msg["content"] if isinstance(next_msg["content"], list) else []
                    result_ids = {b["tool_use_id"] for b in next_content if b.get("type") == "tool_result"}
                    missing_ids = tool_use_ids - result_ids
                    if missing_ids:
                        # 补齐缺失的 tool_result
                        fake_results = [
                            {
                                "type": "tool_result",
                                "tool_use_id": tid,
                                "content": "The tool execution has been interrupted. Please re-initiate the request.",
                                "is_error": True,
                            }
                            for tid in missing_ids
                        ]
                        new_messages.append(msg)
                        new_messages.append(MessagePayload(role=MessageRole.USER,content=fake_results))
                        i += 1
                        continue

        new_messages.append(msg)
        i += 1

    # 判断最后一条是否为Assistant，如果不是则补齐一个空消息
    if new_messages and new_messages[-1]["role"] != MessageRole.ASSISTANT.value:
        new_messages.append(MessagePayload(role=MessageRole.ASSISTANT, content="( Lost reply, please continue )"))

    return new_messages

async def get_or_create_chat(chat_id: uuid.UUID | None, mac: str, db: AsyncSession) -> Chat:
    """
    获取或创建会话
    """
    if chat_id is not None:
        return await chat_crud.get_chat(chat_id, db)
    return await chat_crud.create_chat(Chat(mac=mac), db)

def convert_db_data_to_ai(content: str) -> str | list:
    """DB 中存的是文本；结构化内容存为 JSON 字符串，需解析后交给 Anthropic。"""
    s = content.strip()
    if s[:1] in "[{":
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
    return content

async def get_content_messages(db_messages: list):
    """
    获取 content 类型的 messages，用于继续对话。
    1. 从数据库获取上下文
    2. 获取最后一次 summary 到当前时间的 messages，如果没有就获取所有
    3. 修复 messages 中的数据丢失或中断
    4. 返回 messages
    """
    
    # 先构建完整 messages，再做修复
    raw_messages = []

    # ---------- 获取最后一次汇总的 message 的索引 ----------
    latest_summary_message_index: int | None = None
    for i in range(len(db_messages)-1, -1, -1):
        if db_messages[i].type == MessageType.SUMMARIZE and db_messages[i].role == MessageRole.ASSISTANT:
            latest_summary_message_index = i
            break

    logger.info(f"latest_summary_message_index: {latest_summary_message_index}")

    db_messages = db_messages if latest_summary_message_index is None else db_messages[latest_summary_message_index:]

    # ---------- 转换为 Anthropic 的 messages 格式 ----------
    for msg in db_messages:
        if msg.type == MessageType.SUMMARIZE and msg.role == MessageRole.ASSISTANT:
            raw_messages.append(MessagePayload(role=MessageRole.USER, content=f"[历史对话摘要]\n{msg.content}"))
            raw_messages.append(MessagePayload(role=MessageRole.ASSISTANT, content="已了解历史上下文，继续为您服务。"))
        elif msg.type == MessageType.DEFAULT:
            content = convert_db_data_to_ai(msg.content)
            raw_messages.append(MessagePayload(role=msg.role, content=content))

    # ---------- 修复 messages 中的数据丢失或中断 ----------
    messages = repair_messages(raw_messages)

    return messages



async def compress_context(chat_id: uuid.UUID, messages: list) -> None:
    """
    压缩上下文，将历史对话摘要化
    """
    summary_prompt = AI_SUMMARY_TEXT_PROMPT

    user_history_message = f"""
    用户的对话内容：{json.dumps(messages, ensure_ascii=False)}
    """

    messages = [MessagePayload(role=MessageRole.USER, content= user_history_message)]
    
    try:
        resp = await anthropic_client.messages.create(
            model=settings.AI_MODEL,
            system=[
                {"type": "text", "text": summary_prompt, "cache_control": {"type": "ephemeral"}},
            ],
            messages=messages,
            max_tokens=settings.SUMMARY_MAX_TOKENS,
        )

        usage = resp.usage
        totens = usage.input_tokens + usage.output_tokens

        async with get_db_cm() as db:
            await save_message(chat_id, MessageRole.USER, user_history_message, db, type=MessageType.SUMMARIZE)
            await save_message(chat_id, MessageRole.ASSISTANT, resp.content[0].text, db, totens, MessageType.SUMMARIZE)
    except Exception as e:
        logger.exception(e)    

async def save_ai_response(chat_id: uuid.UUID, ai_response: list, tokens: int, messages: list, db: AsyncSession, message_type: MessageType = MessageType.DEFAULT):
    await save_message(chat_id, MessageRole.ASSISTANT, ai_response, db, tokens, message_type)
    messages.append(MessagePayload(role=MessageRole.ASSISTANT, content=ai_response))

async def save_user_question(chat_id: uuid.UUID, question: str | list, messages: list, db: AsyncSession):
    await save_message(chat_id, MessageRole.USER, question, db)
    messages.append(MessagePayload(role=MessageRole.USER, content=question))

async def save_tool_result(
    chat_id: uuid.UUID, 
    tool_results: list[ToolResult], 
    messages: list, 
    db: AsyncSession,
    before_peq: dict | None = None,
    after_peq: dict | None = None,
    applied: bool = False
):
    tool_results_list = [result.model_dump(exclude_none=True) for result in tool_results]
    logger.info(f"save_tool_result: {tool_results_list}")
    await save_message(chat_id, MessageRole.USER, tool_results_list, db, before_peq=before_peq, after_peq=after_peq, applied=applied)
    messages.append(MessagePayload(role=MessageRole.USER, content=tool_results_list))

async def save_message(
    chat_id: uuid.UUID, role: MessageRole, content: list | str, 
    db: AsyncSession, tokens: int=0, 
    type: MessageType = MessageType.DEFAULT,
    before_peq: str = None,
    after_peq: str = None,
    applied: bool = False
):
    msg: str = json.dumps(content, ensure_ascii=False) if isinstance(content, list) else content

    message = Message(
        chat_id=chat_id, 
        role=role, 
        content=msg, 
        tokens=tokens,
        type=type,
        before_peq=before_peq,
        after_peq=after_peq,
        applied=applied
    )
    await chat_crud.create_message(message, db)

def get_language_name(language:int):
    """获取语言名称"""
    return LANGUAGE_NAME[language]

def print_messages(messages: list):
    print("----------Begin Messages ----------")
    for message in messages:
        print("\t", message["role"], ":\n\t\t", message["content"])
    print("----------End Messages ----------")













def get_device_settings(question: QuestionRequest) -> str:
    return question.device_setting.model_dump_json()

def get_peq_list(question: QuestionRequest) -> str:
    return json.dumps([peq.name for peq in question.device_peq.peq], ensure_ascii=False)

def get_current_peq(question: QuestionRequest) -> str:
    index = question.device_peq.peqSelect
    return question.device_peq.peq[index].model_dump_json()

BACKEND_TOOLS_FUNC = {
    "get_device_settings": get_device_settings,
    "get_peq_list": get_peq_list,
    "get_current_peq": get_current_peq
}





async def handle_tool(contents: list[dict], chat: Chat, messages: list, db: AsyncSession, question: QuestionRequest):
    results = []

    before_peq: dict | None = None
    after_peq: dict | None = None

    for content in contents:
        content_type = content["type"]
        if not content_type == "tool_use":
            continue
        fn_name = content["name"]
        fn_id = content["id"]
        fn_input = content["input"]
        if fn_name in BACKEND_TOOLS:
            result = await execute_backend_tool(
                BackendToolRequest(
                    chat_id=chat.id,
                    fn_id=fn_id,
                    fn_name=fn_name,
                    fn_input=fn_input,
                    messages=messages,
                    question=question,
                )
            )
            results.append(result)
        elif fn_name in FRONTEND_TOOLS:

            if fn_name == "set_peq":
                # 不下发到前端写设备：before/after 落库，由 UI A/B 与用户点击「应用」再调用设备 API
                before_peq = json.loads(get_current_peq(question))
                after_peq = convert_to_dict(fn_input) if isinstance(fn_input, dict) else {}
                result = ToolResult(
                    type="tool_result",
                    tool_use_id=fn_id,
                    content=json.dumps(
                        {
                            "ok": True,
                            "message": "PEQ pending user confirmation (A/B); not written to device yet.",
                        },
                        ensure_ascii=False,
                    ),
                )
                results.append(result)
            else:
                result = await execute_frontend_tool(fn_id)
                yield content
                results.append(handle_tool_result(result))

    await save_tool_result(chat.id, results, messages, db, before_peq=before_peq, after_peq=after_peq)

def handle_tool_result(payload: dict) -> dict:
    ok = payload.get("ok", False)
    content = payload.get("content")
    message = payload.get("message")
    tool_use_id = payload.get("tool_use_id")

    if not ok:
        content = message

    def convert_str(c):
        return json.dumps(c, ensure_ascii=False) if isinstance(c, dict) else str(c)
    
    is_error = None if ok else True
    return ToolResult(
        type="tool_result", 
        tool_use_id=tool_use_id, 
        content=convert_str(content), 
        is_error=is_error
    )

def convert_to_dict(content) -> dict | None:
    if content is None:
        return None
    return json.loads(content) if isinstance(content, str) else content