#!/usr/bin/env bash
# 每日备份 MySQL 与上传图片，保留 7 天（crontab: 0 2 * * * bash /path/to/scripts/backup.sh）
# pipefail：mysqldump 失败时管道后端的 gzip 不会把坏备份"洗白"成正常退出码
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
STAMP=$(date +%F)
DB_FILE="backups/db-${STAMP}.sql.gz"

docker compose exec -T mysql mysqldump -usc -pscpass shicai | gzip > "$DB_FILE"

# 备份有效性检查：gzip 完整 + 压缩包里确有建表/插入语句，坏备份当场报错而不是恢复时才发现
gunzip -t "$DB_FILE"
if ! zgrep -qE "CREATE TABLE|INSERT INTO" "$DB_FILE"; then
  echo "备份内容异常：${DB_FILE} 不含 SQL 语句" >&2
  exit 1
fi

docker compose run --rm -v "$(pwd)/backups:/bk" app tar czf "/bk/uploads-${STAMP}.tgz" /srv/uploads

# 定期演练恢复：gunzip -c db-xxxx.sql.gz | docker compose exec -T mysql -uroot -p<root密码> shicai_restore
find backups -mtime +7 -delete
