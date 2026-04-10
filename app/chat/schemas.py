


from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict

class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    raw_peq: dict | None
    optimized_peq: dict | None
    summary: str | None
    summarized: bool
    created_at: datetime