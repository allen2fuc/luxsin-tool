import json
import logging
import uuid

import anthropic
from fastapi import Depends, Query, Request, BackgroundTasks, APIRouter
from fastapi.responses import EventSourceResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.anthropic import anthropic_client
from app.core.config import settings
from app.core.database import get_db

from app.core.jinja2 import templates

from .constants import anthropic_tools
from . import crud as chat_crud
from .models import DEFAULT_TITLE
from .schemas import ChatRead, MessageRead, QuestionRequest, QuestionResponse, ToolResultRequest
from .services import CONTENT_FORMATTERS, compress_context, generate_title, get_content_messages, get_system_prompt, handle_tool, print_messages, publish_tool_result, get_or_create_chat, save_ai_response, save_user_question, save_tool_result

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

    await publish_tool_result(req.tool_use_id, {**req.content.model_dump(exclude_none=True), "tool_use_id": req.tool_use_id})
    return {"ok": True}


@router.post("/sse/question", response_class=EventSourceResponse)
async def sse(question: QuestionRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # 创建或获取会话
    chat = await get_or_create_chat(question.chat_id, question.device_setting.mac, db)

    # 获取上下文 messages
    messages = await get_content_messages(chat.messages)

    # 将 messages 保存到数据库
    await save_user_question(chat.id, question.question, messages, db)

    print_messages(messages)

    # 多次循环，因为可能需要工具调用多次才能完成任务
    while True:
        # 获取系统提示词
        system_prompt = get_system_prompt(question)

        logger.info(f"system prompt: {system_prompt[:20]}...")

        try:
            # 调用 AI 大模型
            async with anthropic_client.messages.stream(
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
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
                logger.info(f"final message: {final_message}")

                usage = final_message.usage
                tokens = usage.input_tokens + usage.output_tokens

                # 将AI的回复内容格式化
                contents = [
                    formatter(content)
                    for content in final_message.content
                    if (formatter := CONTENT_FORMATTERS.get(content.type, None))
                ]

                logger.info(f"AI Assistant Response: StopReason={final_message.stop_reason}, Length={len(contents)}, Contents={contents}")

                await save_ai_response(chat.id, contents, tokens, messages, db)

                # 工具调用结果处理
                if final_message.stop_reason == "tool_use":
                    async for tool_request in handle_tool(contents, chat, messages, db, question):
                        yield QuestionResponse(type="tool_use", content=tool_request)
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
                        background_tasks.add_task(
                            compress_context, chat.id, messages
                        )

                    if chat.title == DEFAULT_TITLE:
                        background_tasks.add_task(
                            generate_title,
                            chat.id,
                            messages,
                        )
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
