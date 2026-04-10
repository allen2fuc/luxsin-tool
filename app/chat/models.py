from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship, Column, DateTime, JSON, Text, asc

import uuid

class Chat(SQLModel, table=True):
    __tablename__ = "ai_chat"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(default="New Chat", nullable=False)
    mac: str = Field(nullable=False)
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
    # 使用 foreign_key= 字符串；勿使用 Field(ForeignKey(...)) 作为首参，否则 Relationship 无法识别外键
    # 必须与 Chat.__tablename__ 一致（此处为 ai_chat），不能写 chat.id
    chat_id: uuid.UUID = Field(foreign_key="ai_chat.id", nullable=False)
    # 使用 str 而非 Literal：SQLModel 映射 Literal 到列类型时会在部分版本触发 issubclass 非 class 报错
    role: str = Field(nullable=False, max_length=16)
    content: str = Field(sa_column=Column(Text, nullable=False))

    summarized: bool = Field(default=False)
    summary: str | None = Field(sa_column=Column(Text, default=None, nullable=True))
    raw_peq: dict | None = Field(sa_column=Column(JSON, default=None, nullable=True))
    optimized_peq: dict | None = Field(sa_column=Column(JSON, default=None, nullable=True))

    created_at: datetime = Field(default_factory=datetime.now)

    chat: "Chat" = Relationship(back_populates="messages")