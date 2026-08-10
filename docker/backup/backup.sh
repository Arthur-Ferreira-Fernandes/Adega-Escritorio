#!/bin/sh
set -e
mkdir -p /backups
DATA_HORA=$(date +%Y-%m-%d_%H-%M-%S)
ARQUIVO="/backups/adega_${DATA_HORA}.sql.gz"
pg_dump "$DATABASE_URL" | gzip > "$ARQUIVO"
echo "$(date '+%Y-%m-%d %H:%M:%S') — backup criado: $ARQUIVO"
# mantém só os últimos 30 dias, pra não acumular disco indefinidamente
find /backups -name "adega_*.sql.gz" -mtime +30 -delete
