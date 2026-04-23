


from datetime import datetime
from typing import Literal, TypedDict
import uuid

from pydantic import BaseModel, Field

from app.luxsin.schemas import DeviceSetting, DevicePEQ

from .constants import MessageRole, MessageType

class ChatRead(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

class MessageRead(BaseModel):
    id: uuid.UUID
    role: MessageRole = Field(description="消息角色, user: 用户, assistant: 助手")
    content: str = Field(description="消息内容")
    created_at: datetime = Field(description="创建时间")
    type: MessageType = Field(description="0默认消息, 2优化消息")
    before_peq: dict | None = Field(description="优化前PEQ")
    after_peq: dict | None = Field(description="优化后PEQ")
    applied: bool = Field(description="当type为2时, false显示应用, true显示回滚")
    applied_at: datetime | None = Field(description="应用时间")

class QuestionRequest(BaseModel):
    """question：本轮用户输入文本。"""
    question: str
    # language: int = 2  # 0 英文 1 繁体中文 2 简体中文
    # mac: str
    # device: str
    device_setting: DeviceSetting  # 这里可以获取到mac/device/language
    device_peq: DevicePEQ
    chat_id: uuid.UUID | None = None

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