#!/usr/bin/env bash
# 每日备份 MySQL 与上传图片，保留 7 天（crontab: 0 2 * * * bash /path/to/scripts/backup.sh）
set -e
cd "$(dirname "$0")/.."
mkdir -p backups
STAMP=$(date +%F)
docker compose exec -T mysql mysqldump -usc -pscpass shicai | gzip > "backups/db-${STAMP}.sql.gz"
docker compose run --rm -v "$(pwd)/backups:/bk" app tar czf "/bk/uploads-${STAMP}.tgz" /srv/uploads
find backups -mtime +7 -delete
