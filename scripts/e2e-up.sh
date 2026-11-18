#!/usr/bin/env bash
# E2E 环境：构建前端 → FastAPI 托管静态产物 + SQLite + dev-login 旁路。
# 端口默认 13100（13000 上有已报备的旧应用在跑，E2E 用 dev-login 不依赖 CAS 回调域名）。
set -e
cd "$(dirname "$0")/.."

( cd frontend && npm run build )

cd backend
rm -f e2e.db
export DATABASE_URL="sqlite:///./e2e.db"
export DEV_AUTH_ENABLED=1
export UPLOAD_DIR="$PWD/uploads"

# 本机为系统 Python（无 venv），依赖已 pip 装好
python seed.py

PORT="${E2E_PORT:-13100}"
nohup python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
  > /tmp/e2e-uvicorn.log 2>&1 &
echo $! > /tmp/e2e-uvicorn.pid

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/api/health" > /dev/null; then
    echo "backend ready on :$PORT"
    exit 0
  fi
  sleep 0.5
done
echo "backend failed to start"; tail -30 /tmp/e2e-uvicorn.log
exit 1
