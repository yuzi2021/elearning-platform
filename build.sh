#!/usr/bin/env sh
set -eu

python -m pip install --disable-pip-version-check -r requirements.txt
python manage.py collectstatic --noinput
