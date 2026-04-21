


from datetime import datetime
from typing import Literal, TypedDict
import uuid

from pydantic import BaseModel

from .constants import MessageRole, MessageType

class ChatRead(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

class MessageRead(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
    type: MessageType
    before_peq: dict | None = None
    after_peq: dict | None = None
    applied: bool
    applied_at: datetime | None = None

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

class ToolResultPayload(BaseModel):
    ok: bool
    # {message/content: dict | str}
    content: dict | str | None = None
    message: str | None = None

class ToolResultRequest(BaseModel):
    tool_use_id: str
    content: ToolResultPayload

class ToolResult(BaseModel):
    type: str = "tool_result"
    tool_use_id: str
    content: str | list
    is_error: bool | None = None

class MessagePayload(TypedDict):
    role: MessageRole
    content: str | list