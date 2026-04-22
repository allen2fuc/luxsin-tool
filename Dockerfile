# syntax=docker/dockerfile:1.7

# ---------- 构建阶段：使用 uv 官方镜像安装依赖 ----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# 先拷贝依赖锁文件，利用 docker 层缓存
COPY pyproject.toml uv.lock README.md ./

# 安装运行时依赖（不包含项目本身），命中 uv 缓存
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 再拷贝源代码并把项目本身装进 venv
COPY app ./app
COPY static ./static
COPY templates ./templates

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ---------- 运行阶段：使用精简 Python 镜像 ----------
FROM python:3.13-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 仅从 builder 拷贝必要产物
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/static /app/static
COPY --from=builder /app/templates /app/templates

# 数据与日志挂载目录
RUN mkdir -p /app/logs /app/data

EXPOSE 8000

# 生产使用 uvicorn 直接启动（fastapi[standard] 已含 uvicorn）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
