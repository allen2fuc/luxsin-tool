

from datetime import datetime, timedelta
import uuid
from sqlmodel import delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .models import Chat, Message

async def create_chat(chat: Chat, db: AsyncSession, commit: bool = True, refresh: bool = False) -> Chat:
    db.add(chat)
    if commit:
        await db.commit()
    if commit and refresh:
        await db.refresh(chat)
    return chat

async def get_or_create_chat(mac: str, db: AsyncSession):
    chats = await get_chats(mac, db)
    if not chats:
        chat = Chat(mac=mac)
        return await create_chat(chat, db, refresh=True)
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
        await delete_chat_messages(chat.id, db, commit=False)
        await db.delete(chat)
        await db.commit()
        return True
    return False

async def delete_chat_messages(chat_id: uuid.UUID, db: AsyncSession, commit: bool = True):
    stmt = delete(Message).where(Message.chat_id == chat_id)
    await db.exec(stmt)
    if commit:
        await db.commit()

async def get_message(id: uuid.UUID, db: AsyncSession):
    return await db.get(Message, id)

async def create_message(message: Message, db: AsyncSession, refresh: bool = False) -> Message:
    db.add(message)
    await db.commit()
    if refresh:
        await db.refresh(message)
    return message

async def create_message_batch(messages: list[Message], db: AsyncSession):
    db.add_all(messages)
    await db.commit()

async def get_chat_messages(chat_id: uuid.UUID, db: AsyncSession):
    stmt = select(Message).where(Message.chat_id == chat_id, Message.type == 0).order_by(Message.created_at.asc())
    result = await db.exec(stmt)
    return result.all()

async def get_messages(chat_id: uuid.UUID, db: AsyncSession):
    stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
    result = await db.exec(stmt)
    return result.all()

# 增加汇总信息
async def update_message_summary(message_id: uuid.UUID, summary: str, db: AsyncSession):
    message = await db.get(Message, message_id)
    if message:
        message.summary = summary
        message.summary_updated_at = datetime.now()
        await db.commit()
    return None

# 统计mac下最近4个小时的消耗
async def get_recent_consumption(mac: str, db: AsyncSession, hours: int = 4):
    stmt = (
        select(func.sum(Message.tokens).label("total_tokens"))
        .join(Chat, Message.chat_id == Chat.id)
        .where(
            Chat.mac == mac,
            Message.created_at > datetime.now() - timedelta(hours=hours)
        )
    )
    result = await db.exec(stmt)
    return result.one()


# 获取优化记录列表根据chat_id
async def get_optimization_records(chat_id: uuid.UUID, db: AsyncSession):
    stmt = select(Message).where(Message.chat_id == chat_id, Message.type == 2, Message.before_peq.isnot(None), Message.after_peq.isnot(None)).order_by(Message.created_at.desc())
    result = await db.exec(stmt)
    return result.all()

async def update_message_applied(message_id: uuid.UUID, applied: bool, db: AsyncSession):
    message = await db.get(Message, message_id)
    if message:
        message.applied = applied
        message.applied_at = datetime.now()
        await db.commit()
    return None