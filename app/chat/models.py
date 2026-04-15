from datetime import datetime

from sqlmodel import JSON, Field, SQLModel, Relationship, Column, DateTime, SmallInteger, Text, asc

import uuid


DEFAULT_TITLE = "New Chat"

class Chat(SQLModel, table=True):
    __tablename__ = "ai_chat"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(default=DEFAULT_TITLE, nullable=False)
    mac: str = Field(nullable=False)
    total_token_used: int = Field(default=0)
    deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(sa_column=Column(DateTime, default=datetime.now, onupdate=datetime.now))

    messages: list["Message"] = Relationship(
        back_populates="chat", 
        cascade_delete=True,
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan", 
            "order_by": lambda: asc(Message.created_at),
        })
   

class Message(SQLModel, table=True):
    __tablename__ = "ai_message"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chat_id: uuid.UUID = Field(foreign_key="ai_chat.id", nullable=False)
    role: str = Field(nullable=False, max_length=16)
    content: str = Field(sa_column=Column(Text, nullable=False))
    tokens:int = Field(default=0)

    summarized: bool = Field(default=False)

    type: int = Field(sa_column=Column(SmallInteger, default=0, comment="0:默认消息,1:摘要消息,2:优化消息,3:生成标题"))

    # 优化结果
    before_peq: dict | None = Field(sa_column=Column(JSON, nullable=True))
    after_peq: dict | None = Field(sa_column=Column(JSON, nullable=True))
    # 是否应用
    applied: bool = Field(default=False)
    applied_at: datetime | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=datetime.now)

    chat: "Chat" = Relationship(back_populates="messages")


class Config(SQLModel, table=True):
    __tablename__ = "ai_config"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    mac: str = Field(nullable=False, unique=True, index=True)
    base_url: str | None = Field(default=None, nullable=True)
    api_key: str | None = Field(default=None, nullable=True)
    model: str | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(sa_column=Column(DateTime, default=datetime.now, onupdate=datetime.now))