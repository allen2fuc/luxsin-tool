.PHONY: run dev install lock \
        build up up-build down down-v restart logs ps sh health clean \
        install-hooks uninstall-hooks deploy deploy-log

# ========== 本地开发 ==========

## 本地启动（热重载）
run dev:
	uv run fastapi dev

## 安装依赖
install:
	uv sync

## 重新生成 uv.lock
lock:
	uv lock

# ========== Docker ==========

## 构建镜像
build:
	docker compose build

## 启动（后台）
up:
	docker compose up -d

## 构建并启动
up-build:
	docker compose up -d --build

## 停止并移除容器
down:
	docker compose down

## 停止并移除容器+数据卷（危险：会清 sqlite/redis 数据）
down-v:
	docker compose down -v

## 重启 app 服务
restart:
	docker compose restart app

## 查看 app 服务实时日志
logs:
	docker compose logs -f app

## 查看所有服务状态
ps:
	docker compose ps

## 进入 app 容器 shell
sh:
	docker compose exec app /bin/bash

## 查看健康检查状态
health:
	docker inspect luxsin-app --format '{{json .State.Health}}' | python -m json.tool

## 清理本地构建产物（venv 除外）
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# ========== 部署 ==========

## 安装 git 钩子（启用 post-commit 自动部署）
install-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/post-commit scripts/deploy.sh
	@echo "Git hooks installed. core.hooksPath -> .githooks"

## 卸载 git 钩子（恢复默认 .git/hooks）
uninstall-hooks:
	git config --unset core.hooksPath || true
	@echo "Git hooks uninstalled."

## 手动部署（等同一次 post-commit 触发的部署）
deploy:
	./scripts/deploy.sh

## 查看最近部署日志
deploy-log:
	@tail -n 200 .deploy.log 2>/dev/null || echo "No .deploy.log yet."
