#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting build sequence..."

echo "📦 Installing requirements..."
pip install -r requirements.txt

echo "⚙️ Running migrations..."
python manage.py migrate

echo "🧺 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build sequence complete."
