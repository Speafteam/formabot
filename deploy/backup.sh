#!/bin/bash
# Резервная копия базы. Кладите в cron раз в сутки:
#   sudo crontab -e
#   0 4 * * * /opt/formabot/deploy/backup.sh
#
# Копия делается через .backup, а не cp: база работает в режиме WAL,
# и простое копирование одного файла теряет свежие записи.

set -euo pipefail

DB=/opt/formabot/formabot.db
DIR=/opt/formabot/backups
KEEP_DAYS=30

mkdir -p "$DIR"
STAMP=$(date +%Y-%m-%d_%H%M)
sqlite3 "$DB" ".backup '$DIR/formabot_$STAMP.db'"
gzip -f "$DIR/formabot_$STAMP.db"

# Чистим старые копии.
find "$DIR" -name 'formabot_*.db.gz' -mtime "+$KEEP_DAYS" -delete

echo "Копия готова: $DIR/formabot_$STAMP.db.gz"
