


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
    created_at: datetime
    type: int


class OptimizationRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    before_peq: dict
    after_peq: dict
    applied: bool


class ConfigBase(BaseModel):
    base_url: str
    api_key: str
    model: str

class ConfigCreate(ConfigBase):
    mac: str

class ConfigRead(ConfigBase):
    id: uuid.UUID
    mac: str

class ConfigUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None