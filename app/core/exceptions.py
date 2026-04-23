



from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import logging

logger = logging.getLogger(__name__)


def register_exception_handler(app: FastAPI):
    """请求体验证失败时 FastAPI 抛出的是 RequestValidationError，不是 HTTPException(422)。"""

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError):
        # 打印原始请求体
        logger.error("Request validation error: %s", exc.errors(), exc_info=True)
        return JSONResponse(
            status_code=422,
            content={
                "message": "Invalid request parameters",
                "details": exc.errors(),
            },
        )