#!/usr/bin/env bash
set -e

echo "🚀 Starting build sequence..."

echo "🔧 Ensuring system dependencies for WeasyPrint are present..."
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive

  if [ -w /var/lib/apt/lists ]; then
    if apt-get update; then
      apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libffi-dev \
        shared-mime-info
      rm -rf /var/lib/apt/lists/*
    else
      echo "⚠️  Failed to update apt cache; skipping system dependency installation."
    fi
  else
    echo "⚠️  apt cache directory is not writable; skipping system dependency installation."
  fi
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
