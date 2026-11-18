#!/usr/bin/env bash
# 停止 E2E 后端
[ -f /tmp/e2e-uvicorn.pid ] && kill "$(cat /tmp/e2e-uvicorn.pid)" 2>/dev/null && echo stopped
rm -f /tmp/e2e-uvicorn.pid
