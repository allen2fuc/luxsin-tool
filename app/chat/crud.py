

import uuid
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .models import Chat, Message

async def create_chat(chat: Chat, db: AsyncSession):
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat

async def get_or_create_chat(mac: str, db: AsyncSession):
    chats = await get_chats(mac, db)
    if not chats:
        chat = Chat(mac=mac)
        return await create_chat(chat, db)
    return chats[0]

async def get_chats(mac: str, db: AsyncSession):
    stmt = select(Chat).where(Chat.mac == mac).order_by(Chat.created_at.desc())
    result = await db.exec(stmt)
    return result.all()

async def get_chat(id: uuid.UUID, db: AsyncSession):
    return await db.get(Chat, id)

async def delete_chat(id: uuid.UUID, db: AsyncSession):
    chat = await db.get(Chat, id)
    if chat:
        await db.delete(chat)
        await db.commit()
        return True
    return False

async def get_message(id: uuid.UUID, db: AsyncSession):
    return await db.get(Message, id)

async def create_message(message: Message, db: AsyncSession):
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message

async def create_message_batch(messages: list[Message], db: AsyncSession):
    db.add_all(messages)
    await db.commit()

async def get_messages(chat_id: uuid.UUID, db: AsyncSession):
    stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
    result = await db.exec(stmt)
    return result.all()