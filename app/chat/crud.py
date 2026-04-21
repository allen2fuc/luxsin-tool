

from datetime import datetime, timedelta
import uuid
from sqlmodel import delete, func, select, update, or_, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from .models import Chat, Message
from .constants import MessageType

async def create_chat(chat: Chat, db: AsyncSession) -> Chat:
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat

async def update_chat_title(chat_id: uuid.UUID, title: str, db: AsyncSession) -> None:
    stmt = update(Chat).where(Chat.id == chat_id).values(title=title)
    await db.exec(stmt)
    await db.commit()
    return None

async def get_chats(mac: str, db: AsyncSession):
    stmt = select(Chat).where(Chat.mac == mac, Chat.deleted == False).order_by(Chat.created_at.desc())
    result = await db.exec(stmt)
    return result.all()

async def get_chat(id: uuid.UUID, db: AsyncSession):
    stmt = select(Chat).where(Chat.id == id, Chat.deleted == False)
    result = await db.exec(stmt)
    return result.one_or_none()

async def delete_chat(id: uuid.UUID, db: AsyncSession):
    chat = await db.get(Chat, id)
    if chat:
        chat.deleted = True
        chat.deleted_at = datetime.now()
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
    stmt = select(Message).where(
        Message.chat_id == chat_id, 
        or_(Message.type == MessageType.DEFAULT, and_(Message.type == MessageType.OPTIMIZING, Message.before_peq.isnot(None), Message.after_peq.isnot(None)))
    ).order_by(Message.created_at.asc())
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
async def get_recent_consumption(mac: str, db: AsyncSession, hours: int = 4) -> int:
    stmt = (
        select(func.sum(Message.tokens))
        .join(Chat, Message.chat_id == Chat.id)
        .where(
            Chat.mac == mac,
            Message.created_at > datetime.now() - timedelta(hours=hours)
        )
    )
    result = await db.exec(stmt)
    return result.one() or 0


# 获取优化记录列表根据chat_id
async def get_optimization_records(chat_id: uuid.UUID, db: AsyncSession):
    stmt = select(Message).join(Chat, Message.chat_id == Chat.id).where(
        Message.chat_id == chat_id, 
        Chat.deleted == False, 
        Message.type == MessageType.OPTIMIZING, 
        Message.before_peq.isnot(None), 
        Message.after_peq.isnot(None)
    ).order_by(Message.created_at.desc())
    result = await db.exec(stmt)
    return result.all()

async def update_message_applied(message_id: uuid.UUID, applied: bool, db: AsyncSession):
    message = await db.get(Message, message_id)
    if message:
        message.applied = applied
        message.applied_at = datetime.now()
        await db.commit()
    return None