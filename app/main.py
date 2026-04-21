from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.chat import api as chat_api
from app.core.logger import init_logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logger()
    await init_db()
    yield

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_api.router)