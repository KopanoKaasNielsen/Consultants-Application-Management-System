#!/usr/bin/env bash
set -e

echo "🚀 Starting build sequence..."

# Detect Render environment and skip apt-get there
if [ -n "${RENDER:-}" ]; then
  echo "Running on Render – skipping apt-get (read-only filesystem)."
else
  echo "🔧 Ensuring system dependencies for WeasyPrint are present (local/dev only)..."

  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
      libpango-1.0-0 \
      libpangoft2-1.0-0 \
      libcairo2 \
      libcairo2-dev \
      libffi-dev \
      libjpeg-dev \
      zlib1g-dev \
      libssl-dev || echo "⚠️ apt-get failed locally; continuing anyway."
  else
    echo "apt-get not available; skipping system dependency installation."
  fi
fi

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ build.sh completed."
