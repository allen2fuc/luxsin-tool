from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.chat import api as chat_api
from app.core.exceptions import register_exception_handler
from app.core.logger import init_logger
from app.core.middlewares import register_middlewares

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logger()
    await init_db()
    yield

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

register_middlewares(app)
register_exception_handler(app)

app.include_router(chat_api.router)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
