

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


async_engine = create_async_engine("sqlite+aiosqlite:///sqlite.db", echo=True)
async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session

async def init_db():
    async with async_engine.begin() as conn:
        from app.chat.models import Chat, Message
        await conn.run_sync(SQLModel.metadata.create_all)