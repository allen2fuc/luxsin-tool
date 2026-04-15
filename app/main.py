import asyncio
from contextlib import asynccontextmanager
import json
from typing import Literal
import uuid

import anthropic
from fastapi import Body, Depends, FastAPI, Query, Request, BackgroundTasks
from fastapi.responses import EventSourceResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import crud as chat_crud
from app.chat.models import DEFAULT_TITLE, Chat, Message
from app.chat.schemas import ChatRead, ConfigCreate, ConfigUpdate, MessageRead, OptimizationRecordRead
from app.core.anthropic import get_anthropic_client
from app.core.database import get_db, get_db_cm, init_db
from app.core.redis import redis_client
from app.luxsin.constants import AI_EQ_ANALYZE_PROMPT, AI_EQ_OPTIMIZE_PROMPT, AI_SUMMARY_TEXT_PROMPT, AI_SYSTEM_PROMPT, GENERATE_TITLE_PROMPT, LANGUAGE_NAME, anthropic_tools

import logging

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class QuestionRequest(BaseModel):
    """question：本轮用户输入文本。"""
    question: str
    language: int = 2  # 0 英文 1 繁体中文 2 简体中文
    mac: str
    chat_id: uuid.UUID | None = None
    device: str

class QuestionResponse(BaseModel):
    type: Literal["text", "done", "error", "tool_use"]
    content: str | dict | None = None

class OptimizeEqRequest(BaseModel):
    raw_peq: dict
    chat_id: uuid.UUID

class OptimizeEqResponse(BaseModel):
    optimized_peq: dict

class ToolResultRequest(BaseModel):
    tool_use_id: str
    content: dict

@app.get("/")
def chat(request: Request):
    return templates.TemplateResponse(
        request,
        "chat.jinja",
        {
            "title": "Luxsin Chat",
        },
    )

@app.get("/sse/chats", response_model=list[ChatRead])
async def list_chats(mac: str = Query(..., description="Device MAC"), db: AsyncSession = Depends(get_db)):
    chats = await chat_crud.get_chats(mac, db)
    return chats

@app.get("/sse/messages", response_model=list[MessageRead])
async def list_messages(chat_id: uuid.UUID = Query(..., description="Chat ID"), db: AsyncSession = Depends(get_db)):
    """返回指定会话在数据库中的消息列表，供前端刷新或新开页时拉取。"""
    rows = await chat_crud.get_chat_messages(chat_id, db)
    return rows

@app.post("/sse/clear")
async def messages_clear(chat_id: uuid.UUID = Query(..., description="Chat ID"), db: AsyncSession = Depends(get_db)):
    await chat_crud.delete_chat(chat_id, db)
    return JSONResponse({"ok": True, "message": "Messages cleared"})

# 获取最近4个小时的消耗
@app.get("/sse/recent_consumption")
async def get_recent_consumption(mac: str = Query(..., description="Device MAC"), db: AsyncSession = Depends(get_db)):
    consumption = await chat_crud.get_recent_consumption(mac, db, hours=4)
    return JSONResponse({"ok": True, "consumption": consumption})

# 获取优化记录列表
@app.get("/sse/optimization_records", response_model=list[OptimizationRecordRead])
async def get_optimization_records(chat_id: uuid.UUID = Query(..., description="Chat ID"), db: AsyncSession = Depends(get_db)):
    records = await chat_crud.get_optimization_records(chat_id, db)
    return records

# 更新消息的applied状态
@app.post("/sse/update_message_applied")
async def update_message_applied(message_id: uuid.UUID = Query(..., description="Message ID"), applied: bool = Query(..., description="Applied"), db: AsyncSession = Depends(get_db)):
    await chat_crud.update_message_applied(message_id, applied, db)
    return JSONResponse({"ok": True})

@app.patch("/chat/update_config")
async def update_config(config_id: uuid.UUID = Query(..., description="Config ID"), config: ConfigUpdate = Body(..., description="Config"), db: AsyncSession = Depends(get_db)):
    await chat_crud.update_config(config_id, config.model_dump(exclude_unset=True), db)
    return JSONResponse({"ok": True})

@app.get("/chat/get_config")
async def get_config(mac: str = Query(..., description="Device MAC"), db: AsyncSession = Depends(get_db)):
    config = await chat_crud.get_or_create_config(mac, db)
    return {"ok": True, "config": config}

@app.post("/chat/tool_result")
async def receive_tool_result(req: ToolResultRequest):
    ok = req.content.get("ok", False)
    if ok:
        tool_result = {"type": "tool_result", "tool_use_id": req.tool_use_id, "content": req.content.get("content", "")}
    else:
        tool_result = {"type": "tool_result", "tool_use_id": req.tool_use_id, "content": req.content.get("message", "Tool execution failed."), "is_error": True}

    logger.info(f"execute tool result: {tool_result}")
    await _publish_tool_result(req.tool_use_id, tool_result)
    return {"ok": True}

@app.post("/sse/question", response_class=EventSourceResponse)
async def sse(question: QuestionRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # 创建或获取会话
    chat = await _resolve_chat(question, db)

    ai_config = await chat_crud.get_or_create_config(question.mac, db)
    is_custom_client, anthropic_client = get_anthropic_client(ai_config.api_key, ai_config.base_url)

    if is_custom_client:
        logger.info(f"use custom anthropic client for mac: {question.mac}")


    model = ai_config.model or "claude-opus-4-5-20251101"

    # 获取系统提示词
    system_prompt = AI_SYSTEM_PROMPT.substitute(language=LANGUAGE_NAME[question.language], device=question.device)

    # 获取上下文 messages
    messages = await _get_content_messages(question, chat, db)

    print("---------- Messages ----------")
    for message in messages:
        print("\t", message["role"], ":\n\t\t", message["content"])
    print("---------- Messages ----------")

    while True:

        system_prompt = _get_system_prompt(question, messages)

        logger.info(f"system prompt: {system_prompt[:20]}...")

        try:
            # 调用AI大模型
            async with anthropic_client.messages.stream(
                system=system_prompt,
                # 可选模型：claude-3-haiku-20240307
                model=model,
                messages=messages,
                tools=anthropic_tools,
                max_tokens=4096,
            ) as stream:

                async for event in stream:
                    if event.type == "text":
                        yield QuestionResponse(type="text", content=event.text)

                yield QuestionResponse(type="text", content="\n")

                final_message = await stream.get_final_message()
                usage = final_message.usage
                tokens = usage.input_tokens + usage.output_tokens

                contents = [
                    formatter(content)
                    for content in final_message.content
                    if (formatter := CONTENT_FORMATTERS.get(content.type, None))
                ]

                logger.info(f"AI Assistant Response: Length={len(contents)}, Contents={contents}")

                await chat_crud.create_message(Message(
                    chat_id=chat.id, 
                    role="assistant", 
                    content=json.dumps(contents, ensure_ascii=False), 
                    tokens=tokens
                ), db)

                messages.append({"role": "assistant", "content": contents})

                # 如果最后一条消息不是 tool_use，则 根据条件 压缩上下文
                is_normal_stop = final_message.stop_reason != "tool_use"
                if is_normal_stop:
                    await _maybe_compress_context(chat, messages, usage, question.language, background_tasks, anthropic_client, model)
                    await _generate_title(chat, messages, question.language, question.device, background_tasks, anthropic_client, model)
                    yield QuestionResponse(type="done")
                    break

                async for qr in _execute_tools_use(contents, messages, chat, db, anthropic_client, model):
                    yield qr

        except anthropic.APITimeoutError as e:
            logger.exception(e)
            yield QuestionResponse(type="error", content="AI connection timeout. Please try again later.")
            break
        except Exception as e:
            logger.exception(e)
            yield QuestionResponse(type="error", content="Internal server error")
            break


async def _execute_tools_use(contents: list, messages: list, chat: Chat, db: AsyncSession, anthropic_client, model):
    """设备侧工具由前端执行后 POST /chat/tool_result；Redis 唤醒后收集 tool_results（后续可接入第二轮模型调用）。"""
    tool_results: list[dict] = []
    for block in contents:
        if block.get("type") != "tool_use":
            continue
        name = block.get("name")
        tool_use_id = block.get("id")
        tool_input = block.get("input")
        backend_fn = BACKEND_TOOLS_MAP.get(name)
        if backend_fn:
            tool_result = await backend_fn(tool_input, chat.id, db, anthropic_client, model)
            if tool_result["ok"]:
                c = tool_result["content"]
                if isinstance(c, dict):
                    c = json.dumps(c, ensure_ascii=False)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": tool_use_id, "content": c}
                )
            else:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(tool_result["message"]),
                        "is_error": True,
                    }
                )
        else:
            yield QuestionResponse(type="tool_use", content=block)
            tr = await _wait_for_frontend_result(tool_use_id)
            c = (
                tr
                if isinstance(tr, str)
                else json.dumps(tr, ensure_ascii=False)
                if isinstance(tr, dict)
                else str(tr)
            )
            tool_results.append({"type": "tool_result", "tool_use_id": tool_use_id, "content": c})

    messages.append({"role": "user", "content": tool_results})
    db_messgae = Message(chat_id=chat.id, role="user", content=json.dumps(tool_results, ensure_ascii=False))
    await chat_crud.create_message(db_messgae, db)
            
async def _maybe_compress_context(chat: Chat, messages: list, usage, language: int, background_tasks: BackgroundTasks, anthropic_client, model) -> None:
    tokens = usage.input_tokens + usage.output_tokens

    logger.info(f"maybe_compress_context: chat_id={chat.id}, tokens={tokens}, messages={len(messages)}")
    if tokens < 6000 or len(messages) < 11:
        return

    logger.info(f"maybe_compress_context: compressing context")

    async def _compress_context(messages: list, language: int, chat_id: uuid.UUID):

        summary_prompt = AI_SUMMARY_TEXT_PROMPT.substitute(language=LANGUAGE_NAME[language])

        user_history_message = f"""
        用户的对话内容：{json.dumps(messages, ensure_ascii=False)}
        """

        messages = [{"role": "user", "content": user_history_message}]
        
        try:
            resp = await anthropic_client.messages.create(
                model=model,
                system=summary_prompt,
                messages=messages,
                max_tokens=4096,
            )

            content = resp.content
            usage = resp.usage

            async with get_db_cm() as db:
                summary = json.dumps(resp.content[0].text, ensure_ascii=False) if content else ""
                db_messages = [
                    Message(chat_id=chat_id, role="user", content=user_history_message, type=1),
                    Message(chat_id=chat_id, role="assistant", content=summary, summarized=True, tokens=usage.input_tokens + usage.output_tokens, type=1),
                ]
                await chat_crud.create_message_batch(db_messages, db)
        except Exception as e:
            logger.exception(e)

    background_tasks.add_task(_compress_context, messages, language, chat.id)




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
    


def _convert_db_data_to_anthropic(content: str) -> str | list:
    """DB 中存的是文本；结构化内容存为 JSON 字符串，需解析后交给 Anthropic。"""
    text = content.strip()
    if text.startswith("[{") and text.endswith("}]"):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return content

async def _resolve_chat(question: QuestionRequest, db: AsyncSession) -> Chat:
    if question.chat_id:
        chat = await chat_crud.get_chat(question.chat_id, db)
        if chat:
            return chat
    # chat_id 为空时显式创建新会话（支持前端“+ 新建会话”）
    return await chat_crud.create_chat(Chat(mac=question.mac), db, refresh=True)


async def _get_content_messages(question: QuestionRequest, chat: Chat, db: AsyncSession):
    """
    获取 content 类型的 messages，用于继续对话。
    1. 从数据库获取上下文
    2. 获取最后一次 summary 到当前时间的 messages，如果没有就获取所有
    3. 修复 messages 中的数据丢失或中断
    4. 返回 messages
    """
    
    # 先构建完整 messages，再做修复
    raw_messages = []

    db_messages = chat.messages

    # ---------- 获取最后一次汇总的 message 的索引 ----------
    latest_summary_message_index = 0
    for i in range(len(db_messages)-1, -1, -1):
        if db_messages[i].summarized:
            latest_summary_message_index = i
            break

    db_messages = db_messages if latest_summary_message_index == 0 else db_messages[latest_summary_message_index:]

    # ---------- 转换为 Anthropic 的 messages 格式 ----------
    for msg in db_messages:
        if msg.summarized:
            raw_messages.append({"role": "user", "content": f"[历史对话摘要]\n{msg.content}"})
            raw_messages.append({"role": "assistant", "content": "已了解历史上下文，继续为您服务。"})
        elif msg.type == 2:
            continue
        else:
            content = _convert_db_data_to_anthropic(msg.content)
            raw_messages.append({"role": msg.role, "content": content})

    raw_messages.append({"role": "user", "content": question.question})

    # ---------- 修复 messages 中的数据丢失或中断 ----------
    messages = _repair_messages(raw_messages)


    logger.info(f"user input message: {question.question}")

    # ---------- 将 messages 保存到数据库 ----------
    await chat_crud.create_message(Message(
        chat_id=chat.id, 
        role="user", 
        content=question.question
    ), db)

    return messages

def _repair_messages(messages: list) -> list:
    """
    修复 messages 中的数据丢失或中断。
    1. assistant 消息含 tool_use，检查下一条是否有对应 tool_result, 如果缺失则补齐。
    2. 连续相同 role，合并内容
    3. 返回修复后的 messages
    """

    if not messages:
        return messages

    sanitized = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        content = msg["content"]
        role = msg["role"]

        # 1. assistant 消息含 tool_use，检查下一条是否有对应 tool_result
        if role == "assistant":
            content_list = content if isinstance(content, list) else []
            tool_use_ids = {b["id"] for b in content_list if b.get("type") == "tool_use"}

            if tool_use_ids:
                next_msg = messages[i + 1] if i + 1 < len(messages) else None
                result_ids = set()

                if next_msg and next_msg["role"] == "user":
                    next_content = next_msg["content"] if isinstance(next_msg["content"], list) else []
                    result_ids = {
                        b["tool_use_id"]
                        for b in next_content
                        if b.get("type") == "tool_result"
                    }

                missing_ids = tool_use_ids - result_ids
                if missing_ids:
                    sanitized.append(msg)
                    # 补齐缺失的 tool_result
                    fake_results = [
                        {
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": "工具执行被中断，请重新发起请求。",
                            "is_error": True,
                        }
                        for tid in missing_ids
                    ]
                    sanitized.append({"role": "user", "content": fake_results})
                    i += 1
                    continue

        # 2. 连续相同 role，合并内容
        if sanitized and sanitized[-1]["role"] == role:
            if role == "user":
                # assistant 回复丢失，插入占位再追加当前 user
                sanitized.append({
                    "role": "assistant",
                    "content": "（回复丢失）"
                })
                sanitized.append(msg)
            elif role == "assistant":
                # 合并两条 assistant
                prev = sanitized[-1]
                prev_content = prev["content"] if isinstance(prev["content"], list) else [{"type": "text", "text": prev["content"]}]
                cur_content = content if isinstance(content, list) else [{"type": "text", "text": content}]
                prev["content"] = prev_content + cur_content
            i += 1
            continue

        sanitized.append(msg)
        i += 1

    return sanitized



async def _publish_tool_result(tool_use_id: str, content: dict):
    channel = f"tool_result:{tool_use_id}"
    await redis_client.set(channel, json.dumps(content, ensure_ascii=False), ex=60)
    await redis_client.publish(channel, "ready")


# 等待前端回传结果
async def _wait_for_frontend_result(tool_use_id: str, timeout: int = 30) -> dict:
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
                        return json.loads(result)
            finally:
                await pubsub.unsubscribe(channel)
                await redis_client.delete(channel)
    
    try:
        return await asyncio.wait_for(_wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": "Access to tool execution timed out.", "is_error": True}


def _get_system_prompt(question: QuestionRequest, messages: list) -> str:
    
    index = 0
    for i in range(len(messages)-1, -1, -1):
        if index > 3:  # 最多往前看5条消息
            break

        content = messages[i]["content"]
        role = messages[i]["role"]

        if role == "assistant" and isinstance(content, list):
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name")
                if tool_name == "optimize_eq":
                    return AI_EQ_OPTIMIZE_PROMPT
                elif tool_name == "get_current_peq":
                    return AI_EQ_ANALYZE_PROMPT.substitute(language=LANGUAGE_NAME[question.language])

        index+=1

    return AI_SYSTEM_PROMPT.substitute(language=LANGUAGE_NAME[question.language], device=question.device)


async def _optimize_eq(raw_peq: dict, chat_id: uuid.UUID, db: AsyncSession, anthropic_client, model) -> dict:
    """
    当遇到非device工具时，调用此接口。比如优化EQ、摘要等。
    """

    user_input_message = f"My current PEQ settings:\n{json.dumps(raw_peq, indent=2, ensure_ascii=False)}\n\nPlease help optimize this EQ."

    user_message = [{"role": "user", "content": user_input_message}]

    try:

        resp = await anthropic_client.messages.create(
            system=AI_EQ_OPTIMIZE_PROMPT,
            model=model,
            messages=user_message,
            max_tokens=8192,
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "brand": {"type": "string"},
                            "model": {"type": "string"},
                            "filters": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "integer"},
                                        "fc": {"type": "number"},
                                        "gain": {"type": "number"},
                                        "q": {"type": "number"},
                                    },
                                    "required": ["type", "fc", "gain", "q"],
                                    "additionalProperties": False,
                                },
                            },
                            "preamp": {"type": "number"},
                            "canDel": {"type": "number"},
                            "autoPre": {"type": "number"},
                        },
                        "required": ["name", "brand", "model", "filters", "preamp", "canDel", "autoPre"],
                        "additionalProperties": False,
                    },
                }
            },
        )

        result = resp.content[0].text if resp.content else "{}"
        optimized_peq = json.loads(result) if result else {}

        db_messages = [
            Message(chat_id=chat_id, role="user", content=user_input_message, tokens=resp.usage.input_tokens, type=2),
            Message(chat_id=chat_id, role="assistant", content=result, tokens=resp.usage.output_tokens, type=2, before_peq=raw_peq, after_peq=optimized_peq),
        ]

        await chat_crud.create_message_batch(db_messages, db)

        return {"ok": True, "content": optimized_peq, "raw_peq": raw_peq}
    except Exception as e:
        logger.exception(e)
        return {"ok": False, "message": "Tool execution failed, error reason: " + str(e)}


BACKEND_TOOLS_MAP = {
    "optimize_eq": _optimize_eq,
}



# 生成标题
async def _generate_title(chat: Chat, messages: list, language: int, device: str, background_tasks: BackgroundTasks, anthropic_client, model) -> None:

    if chat.title != DEFAULT_TITLE:
        return None

    async def _generate_title_task(chat_id: uuid.UUID, messages: list, language: int):

        try:
            generate_title_prompt = GENERATE_TITLE_PROMPT.substitute(language=LANGUAGE_NAME[language])

            # 用户输入的信息，将用户输入的消息合并（content 可能是 list/dict，需要先转字符串）
            merged_user_contents = []
            for msg in messages:
                if msg.get("role") != "user":
                    continue
                c = msg.get("content", "")
                if isinstance(c, str):
                    merged_user_contents.append(c)
               
            user_input_message = "User input messages:\n" + "\n".join(merged_user_contents)

            user_message = [{"role": "user", "content": user_input_message}]

            resp = await anthropic_client.messages.create(
                system=generate_title_prompt,
                model=model,
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

            logger.info(f"generate title: {chat_id} {result}")

            async with get_db_cm() as db:

                if replaced_result != DEFAULT_TITLE and "New Title" not in replaced_result:
                    await chat_crud.update_chat_title(chat_id, replaced_result, db)

                await chat_crud.create_message_batch([
                    Message(chat_id=chat_id, role="user", content=user_input_message, tokens=resp.usage.input_tokens, type=3),
                    Message(chat_id=chat_id, role="assistant", content=result, tokens=resp.usage.output_tokens, type=3),
                    ], db)

                return None

        except Exception as e:
            logger.exception(e)
    
    background_tasks.add_task(_generate_title_task, chat.id, messages, language)

    return None