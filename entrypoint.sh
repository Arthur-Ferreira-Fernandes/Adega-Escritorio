#!/bin/sh
set -e

host=$(echo "$DATABASE_URL" | sed -E 's#.*@([^:/]+).*#\1#')
port=$(echo "$DATABASE_URL" | sed -E 's#.*:([0-9]+)/.*#\1#')

echo "Aguardando o banco de dados em ${host}:${port}..."
while ! nc -z "$host" "$port"; do
  sleep 1
done
echo "Banco de dados disponível."

mkdir -p /app/logs

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
