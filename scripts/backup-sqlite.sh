#!/usr/bin/env bash
# 每日备份 SQLite 数据库（一致性快照）与上传图片，保留 14 天
# crontab: 30 2 * * * bash /home/aitest/scydhqc/scripts/backup-sqlite.sh
set -euo pipefail
BASE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE/backend"
mkdir -p "$BASE/backups"
STAMP=$(date +%F)

# sqlite3 CLI 不一定装了，用 venv 里的 python 做一致性备份（WAL 模式下直接 cp 不安全）
.venv/bin/python - "$BASE/backups/db-${STAMP}.db" <<'EOF'
import sqlite3, sys
src = sqlite3.connect("scydhqc.db")
dst = sqlite3.connect(sys.argv[1])
with dst:
    src.backup(dst)
src.close(); dst.close()
print("db backup ok")
EOF

if [ -d "$BASE/backend/uploads" ]; then
  tar czf "$BASE/backups/uploads-${STAMP}.tgz" -C "$BASE/backend" uploads
fi

find "$BASE/backups" -mtime +14 -delete
echo "backup done: $STAMP"
