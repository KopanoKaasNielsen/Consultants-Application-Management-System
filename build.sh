#!/usr/bin/env bash
set -euo pipefail

echo "📦 Installing requirements..."
pip install -r requirements.txt

echo "⚙️ Running migrations..."
python manage.py migrate

echo "🧺 Collecting static files..."
python manage.py collectstatic --noinput
