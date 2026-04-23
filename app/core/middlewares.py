

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import time
import logging
logger = logging.getLogger(__name__)

def register_middlewares(app: FastAPI):

    LOG_REQUEST_IGNORE_PATHS = {"/health", "/metrics", "/docs", "/openapi.json"}

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request: {request.method} {request.url} {request.client.host} {e}")
            raise

        if request.url.path in LOG_REQUEST_IGNORE_PATHS:
            return response

        end_time = time.time()
        logger.info(f"Request: {request.method} {request.url} {request.client.host} {response.status_code} {end_time - start_time}s")

        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")