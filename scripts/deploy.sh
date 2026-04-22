#!/usr/bin/env bash
# 自动部署脚本：rsync 同步代码到远端，然后重启 docker compose。
# 默认只在 DEPLOY_BRANCH (main) 分支触发；通过环境变量可覆盖。

set -euo pipefail

# ========== 配置（可通过环境变量覆盖）==========
SSH_TARGET="${DEPLOY_SSH_TARGET:-ubuntu@ec2-18-184-205-87.eu-central-1.compute.amazonaws.com}"
SSH_KEY="${DEPLOY_SSH_KEY:-$HOME/.ssh/id_ed25519}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/data/project/luxsin-tool}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

# ========== 预检查 ==========
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "$DEPLOY_BRANCH" ]]; then
  echo "[deploy] skip: current branch '$BRANCH' != DEPLOY_BRANCH '$DEPLOY_BRANCH'"
  exit 0
fi

if [[ ! -f "$SSH_KEY" ]]; then
  echo "[deploy] ssh key not found: $SSH_KEY" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "[deploy] rsync not installed locally" >&2
  exit 1
fi

SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)

# 镜像 tag = 当前提交的短 SHA；工作区脏时追加 -dirty 避免和干净版冲突
IMAGE_TAG="$(git rev-parse --short=7 HEAD)"
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  IMAGE_TAG="${IMAGE_TAG}-dirty"
fi

echo "[deploy] ===== start at $(date '+%F %T') ====="
echo "[deploy] target   : $SSH_TARGET:$REMOTE_DIR"
echo "[deploy] branch   : $BRANCH"
echo "[deploy] commit   : $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
echo "[deploy] image tag: luxsin-tool:$IMAGE_TAG"

# ========== 确保远端目录存在 ==========
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "mkdir -p '$REMOTE_DIR'"

# ========== 同步代码 ==========
# 说明：排除不该部署的文件；.env 不在仓库里，也不同步（由服务器自备）
rsync -az --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='logs/' \
  --exclude='*.db' \
  --exclude='*.sqlite*' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='node_modules/' \
  --exclude='.deploy.log' \
  --exclude='.idea/' \
  --exclude='.vscode/' \
  --exclude='.DS_Store' \
  "$REPO_ROOT/" \
  "$SSH_TARGET:$REMOTE_DIR/"

# ========== 远端构建 & 重启 ==========
# IMAGE_TAG 通过 ssh 的环境变量传递（不依赖远端 SendEnv/AcceptEnv 配置，直接拼命令行）
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" \
  "IMAGE_TAG='$IMAGE_TAG' REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"

if [[ ! -f .env ]]; then
  echo "[remote] WARN: .env not found in $REMOTE_DIR (compose will likely fail)."
fi

export IMAGE_TAG

echo "[remote] building image: luxsin-tool:$IMAGE_TAG"
docker compose up -d --build

# 给本次 SHA 镜像补一个 latest 别名，方便不带 IMAGE_TAG 时也能用
docker image tag "luxsin-tool:$IMAGE_TAG" "luxsin-tool:latest"

echo "[remote] current images:"
docker images --filter=reference='luxsin-tool' --format 'table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}'

echo "[remote] services:"
docker compose ps
REMOTE

echo "[deploy] ===== done at $(date '+%F %T') ====="
