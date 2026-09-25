#!/usr/bin/env sh
set -eu

python manage.py migrate --noinput

if [ "${SEED_DEMO_DATA:-True}" = "True" ] || [ "${SEED_DEMO_DATA:-True}" = "true" ]; then
    python manage.py seed_demo
fi

exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
