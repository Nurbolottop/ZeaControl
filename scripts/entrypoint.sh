#!/bin/sh
set -e

echo "Начало инициализации базы данных..."

# Подождем немного, чтобы убедиться, что сеть готова
echo "Подождем 2 секунды..."
sleep 2

# Ожидание доступности базы данных
echo "Ожидание доступности базы данных..."
until nc -z -v -w30 $POSTGRES_HOST $POSTGRES_PORT
do
  echo "Waiting for PostgreSQL database connection..."
  sleep 1
done

echo "База данных доступна. Создаём миграции..."
python manage.py makemigrations --noinput

echo "Применяем миграции..."
python manage.py migrate --noinput

echo "Собираем статические файлы..."
python manage.py collectstatic --noinput


# Запускаем переданную команду
exec "$@"