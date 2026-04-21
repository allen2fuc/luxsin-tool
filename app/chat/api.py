import json
import logging
import uuid

import anthropic
from fastapi import Depends, Query, Request, BackgroundTasks, APIRouter
from fastapi.responses import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.anthropic import anthropic_client
from app.core.config import settings
from app.core.database import get_db

from app.core.jinja2 import templates
from app.luxsin.constants import BACKEND_TOOLS, FRONTEND_TOOLS, anthropic_tools

from . import crud as chat_crud
from .models import DEFAULT_TITLE
from .schemas import ChatRead, MessageRead, QuestionRequest, QuestionResponse, ToolResultRequest
from .services import CONTENT_FORMATTERS, compress_context, execute_backend_tool, execute_frontend_tool, generate_title, get_content_messages, get_system_prompt, publish_tool_result, get_or_create_chat, save_ai_response, save_user_question, save_tool_result

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/")
def chat(request: Request):
    return templates.TemplateResponse(
        request, "chat.jinja",
        {"title": "Luxsin Chat"},
    )

@router.get("/sse/chats", response_model=list[ChatRead], description="获取会话信息")
async def list_chats(mac: str = Query(..., description="Device MAC"), db: AsyncSession = Depends(get_db)):
    return await chat_crud.get_chats(mac, db)

@router.get("/sse/messages", response_model=list[MessageRead], description="获取消息内容")
async def list_messages(chat_id: uuid.UUID = Query(..., description="Chat ID"), db: AsyncSession = Depends(get_db)):
    return await chat_crud.get_chat_messages(chat_id, db)

@router.post("/sse/clear", description="清理会话消息")
async def messages_clear(chat_id: uuid.UUID = Query(..., description="Chat ID"), db: AsyncSession = Depends(get_db)):
    await chat_crud.delete_chat(chat_id, db)
    return {"ok": True, "message": "Messages cleared"}

@router.get("/sse/recent_consumption", description="获取最近4个小时的消耗")
async def get_recent_consumption(mac: str = Query(..., description="Device MAC"), db: AsyncSession = Depends(get_db)):
    consumption: int = await chat_crud.get_recent_consumption(mac, db, hours=4)
    return {"ok": True, "consumption": consumption}

@router.post("/sse/update_message_applied", description="更新消息的applied状态")
async def update_message_applied(message_id: uuid.UUID = Query(..., description="Message ID"), applied: bool = Query(..., description="Applied"), db: AsyncSession = Depends(get_db)):
    await chat_crud.update_message_applied(message_id, applied, db)
    return {"ok": True}

@router.post("/chat/tool_result")
async def receive_tool_result(req: ToolResultRequest):
    ok = req.content.ok
    content = req.content.content
    message = req.content.message

    logger.info(f"receive_tool_result: {req.tool_use_id} {ok} {content} {message}")

    def convert_str(c):
        if isinstance(c, dict) or isinstance(c, list):
            return json.dumps(c, ensure_ascii=False)
        elif isinstance(c, str):
            return c
        else:
            return str(c)
    
    converted_content = convert_str(content) if ok else message

    tool_result = {
        "type": "tool_result",
        "tool_use_id": req.tool_use_id,
        "content": converted_content,
    }
    if not ok:
        tool_result["is_error"] = True

    await publish_tool_result(req.tool_use_id, tool_result)
    return {"ok": True}


@router.post("/sse/question", response_class=EventSourceResponse)
async def sse(question: QuestionRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # 创建或获取会话
    chat = await get_or_create_chat(question.chat_id, question.mac, db)

    # 获取上下文 messages
    messages = await get_content_messages(chat.messages)

    # 将 messages 保存到数据库
    await save_user_question(chat.id, question.question, messages, db)

    # 多次循环，因为可能需要工具调用多次才能完成任务
    while True:
        # 打印 messages 用于调试
        print("----------Begin Messages ----------")
        for message in messages:
            print("\t", message["role"], ":\n\t\t", message["content"])
        print("----------End Messages ----------")

        # 获取系统提示词
        system_prompt = get_system_prompt(question, messages)

        logger.info(f"system prompt: {system_prompt[:20]}...")

        try:
            # 调用 AI 大模型
            async with anthropic_client.messages.stream(
                system=system_prompt,
                model=settings.AI_MODEL,
                messages=messages,
                tools=anthropic_tools,
                max_tokens=settings.AI_MAX_TOKENS,
            ) as stream:

                async for event in stream:
                    if event.type == "text":
                        yield QuestionResponse(type="text", content=event.text)

                yield QuestionResponse(type="text", content="\n")

                final_message = await stream.get_final_message()
                usage = final_message.usage
                tokens = usage.input_tokens + usage.output_tokens

                # 将AI的回复内容格式化
                contents = [
                    formatter(content)
                    for content in final_message.content
                    if (formatter := CONTENT_FORMATTERS.get(content.type, None))
                ]

                logger.info(f"AI Assistant Response: StopReason={final_message.stop_reason}, Length={len(contents)}, Contents={contents}")

                # 将AI的回复内容保存到数据库
                await save_ai_response(chat.id, contents, tokens, messages, db)

                # 工具调用结果处理
                if final_message.stop_reason == "tool_use":
                    results = []
                    for content in contents:
                        if not content["type"] == "tool_use":
                            continue
                        name = content["name"]
                        if name in BACKEND_TOOLS:
                            result = await execute_backend_tool(content["id"],name, content["input"], chat.id, db)
                            results.append(result.model_dump(exclude_none=True))
                        elif name in FRONTEND_TOOLS:
                            yield QuestionResponse(type="tool_use", content=content)
                            result = await execute_frontend_tool(content["id"])
                            results.append(result.model_dump(exclude_none=True))
                    await save_tool_result(chat.id, results, messages, db)

                    logger.info(f"save tool result. chat_id={chat.id}")
                elif final_message.stop_reason == "max_tokens":
                    logger.warning(f"Response was cut off at token limit. chat_id={chat.id}")
                    break
                # 如果最后一条消息是 end_turn 且没有内容，则保存用户问题，并继续循环
                elif final_message.stop_reason == "end_turn" and not final_message.content:
                    await save_user_question(chat.id, "Please continue", messages, db)
                elif final_message.stop_reason == "model_context_window_exceeded":
                    logger.warning(f"Response reached model's context window limit. chat_id={chat.id}")
                    break
                elif final_message.stop_reason == "pause_turn":
                    logger.warning(f"Continue the conversation by sending the response back. chat_id={chat.id}")
                    break
                elif final_message.stop_reason == "refusal":
                    logger.warning(f"Claude was unable to process this request. chat_id={chat.id}")
                    break
                else:
                    logger.warning(f"End turn stream reason: {final_message.stop_reason}")
                    # Handle end_turn and other cases
                    tokens = usage.input_tokens + usage.output_tokens
                    if tokens >= settings.SUMMARY_MAX_TOKENS or len(messages) >= settings.SUMMARY_MAX_MESSAGES:
                        logger.info(f"compress_context: chat_id={chat.id}, tokens={tokens}, messages={len(messages)}")
                        background_tasks.add_task(compress_context, chat.id, messages, question.language)

                    if chat.title == DEFAULT_TITLE:
                        background_tasks.add_task(
                            generate_title, chat.id, messages, question.language, question.device)
                    break

        except anthropic.APITimeoutError as e:
            logger.exception(e)
            yield QuestionResponse(type="error", content="AI connection timeout. Please try again later.")
            break
        except Exception as e:
            logger.exception(e)
            yield QuestionResponse(type="error", content="Internal server error")
            break

        logger.info(f"Continue the conversation by sending the response back. chat_id={chat.id}")

    yield QuestionResponse(type="done")
