from contextlib import asynccontextmanager
import json
from typing import Literal
import uuid

from anthropic import AsyncAnthropic
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import EventSourceResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import crud as chat_crud
from app.chat.models import Chat, Message
from app.chat.schemas import ChatRead, MessageRead
from app.core.database import get_db, init_db
from app.luxsin.constants import AI_EQ_ANALYZE_PROMPT, AI_EQ_OPTIMIZE_PROMPT, AI_SYSTEM_PROMPT, LANGUAGE_NAME, TOOLS

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class QuestionRequest(BaseModel):
    """question：新一轮用户输入或 tool_result 列表。continue_pending 为 True 时不写入 question，仅在已有对话末尾 user 上继续生成。"""
    question: str | list[dict] | None = None
    continue_pending: bool = False
    tool_names: list[str] | None = None
    language: int = 2  # 0 英文 1 繁体中文 2 简体中文
    mac: str
    chat_id: uuid.UUID | None = None
    device: str

class QuestionResponse(BaseModel):
    type: Literal["text", "done", "error"]
    content: str | list[dict]

class OptimizeEqRequest(BaseModel):
    raw_peq: dict

class OptimizeEqResponse(BaseModel):
    optimized_peq: dict

class SummarizeRequest(BaseModel):
    language: int = 2

class SummarizeResponse(BaseModel):
    summary: str

class MessagePayload(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[dict]

client = AsyncAnthropic(
    api_key="sk_EMCkI-4qXUXj2CkXG-Y6_yat65djagHfBQK0oCWhd14", 
    base_url="https://api.jiekou.ai/anthropic"
)

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
    rows = await chat_crud.get_messages(chat_id, db)
    return rows

@app.post("/sse/clear")
async def messages_clear(chat_id: uuid.UUID = Query(..., description="Chat ID"), db: AsyncSession = Depends(get_db)):
    await chat_crud.delete_chat(chat_id, db)
    return JSONResponse({"ok": True, "message": "Messages cleared"})


@app.post("/sse/optimize_eq")
async def optimize_eq(params: OptimizeEqRequest):
    """
    当遇到非device工具时，调用此接口。比如优化EQ、摘要等。
    """

    msg = [{"role": "user", "content": f"My current PEQ settings:\n{json.dumps(params.raw_peq, indent=2)}\n\nPlease help optimize this EQ."}]

    response = await client.messages.create(
        system=AI_EQ_OPTIMIZE_PROMPT,
        model="claude-opus-4-5-20251101",
        messages=msg,
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
                        "filters": {"type": "array"},
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

    result = response.content[0].text

    logger.info(f"sse_tool result: {result}")

    optimized_peq = json.loads(result)

    return OptimizeEqResponse(optimized_peq=optimized_peq)

@app.post("/sse/summarize")
async def summarize(params: SummarizeRequest):
    """占位：摘要需指定 chat_id 并从数据库组装 transcript 后再接入 AI_SUMMARY_TEXT_PROMPT。"""
    raise HTTPException(status_code=501, detail="summarize_not_implemented")

def _stored_content_to_api(content: str) -> str | list:
    """DB 中存的是文本；结构化内容存为 JSON 字符串，需解析后交给 Anthropic。"""
    if not isinstance(content, str):
        return content
    s = content.strip()
    if s.startswith("[") or s.startswith("{"):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return content


async def resolve_chat(question: QuestionRequest, db: AsyncSession) -> Chat:
    if question.chat_id:
        chat = await chat_crud.get_chat(question.chat_id, db)
        if not chat or chat.mac != question.mac:
            raise HTTPException(status_code=404, detail="chat_not_found")
        return chat
    return await chat_crud.get_or_create_chat(question.mac, db)


async def _continue_pending_messages(question: QuestionRequest, chat: Chat, db: AsyncSession):
    messages = []
    for msg in chat.messages:
        c = _stored_content_to_api(msg.content)
        messages.append({"role": msg.role, "content": c})
    if question.continue_pending:
        if not messages or messages[-1].get("role") != "user":
            raise HTTPException(
                status_code=400,
                detail={"error": "no_pending_user_message"},
            )
    else:
        if question.question is None:
            raise HTTPException(
                status_code=400,
                detail={"error": "question_required"},
            )
        messages.append({"role": "user", "content": question.question})
        chat.messages.append(
            Message(
                chat_id=chat.id,
                role="user",
                content=json.dumps(question.question)
                if isinstance(question.question, list)
                else question.question,
            )
        )
        await db.commit()
        await db.refresh(chat)
    return messages


@app.post("/sse/question", response_class=EventSourceResponse)
async def sse(question: QuestionRequest, db: AsyncSession = Depends(get_db)):
    chat = await resolve_chat(question, db)

    messages = await _continue_pending_messages(question, chat, db)

    system_prompt = _get_system_prompt(question)

    try:

        async with client.messages.stream(
            system=system_prompt,
            # 可选模型：claude-3-haiku-20240307
            model="claude-opus-4-5-20251101",
            messages=messages,
            tools=TOOLS,
            max_tokens=4096,
        ) as stream:

            async for event in stream:
                if event.type == "text":
                    yield QuestionResponse(type="text", content=event.text)
            yield QuestionResponse(type="text", content="\n")

            final_message = await stream.get_final_message()
            contents = []
            for content in final_message.content:
                if content.type == "tool_use":
                    contents.append(
                        {
                            "type": "tool_use",
                            "id": content.id,
                            "name": content.name,
                            "input": content.input,
                        }
                    )
                elif content.type == "text":
                    contents.append({"type": "text", "text": content.text})
                else:
                    logger.warning(f"Other: {content}")

            chat.messages.append(
                Message(chat_id=chat.id, role="assistant", content=json.dumps(contents))
            )
            await db.commit()

            yield  QuestionResponse(type="done", content=contents)
    except Exception as e:
        logger.exception(e)
        yield QuestionResponse(type="error", content=str(e))


def _get_system_prompt(question: QuestionRequest):
    if question.tool_names and "get_current_peq" in question.tool_names:
        return AI_EQ_ANALYZE_PROMPT.substitute(language=LANGUAGE_NAME[question.language])
    else:
        return AI_SYSTEM_PROMPT.substitute(language=LANGUAGE_NAME[question.language])
