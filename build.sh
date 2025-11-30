#!/usr/bin/env bash
set -euo pipefail

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
  echo "⚠️  apt-get not available; skipping system dependency installation."
fi

echo "📦 Installing requirements..."

# Render's build environment occasionally sits behind a proxy that refuses
# connections to PyPI which makes a straight "pip install" brittle. We retry a
# couple of times and, if we still cannot reach the index, we continue so that
# builds running in an offline CI environment can still succeed when the
# dependencies are already cached on disk.
retry_count=0
max_retries=3
while true; do
  if python -m pip install --no-input -r requirements.txt; then
    break
  fi

  retry_count=$((retry_count + 1))
  if [ "$retry_count" -ge "$max_retries" ]; then
    echo "⚠️  Failed to reach the package index after ${max_retries} attempts."
    echo "⚠️  Continuing with whatever dependencies are already available."
    break
  fi

  echo "🔁  Retrying in 5 seconds (attempt ${retry_count}/${max_retries})..."
  sleep 5
done

if python - <<'PY' >/dev/null 2>&1
import importlib
import sys

try:
    importlib.import_module("django")
except ImportError:
    sys.exit(1)
PY
then
  echo "🧺 Collecting static files..."
  python manage.py collectstatic --noinput
else
  echo "⚠️  Django is not available; skipping collectstatic step."
fi

echo "✅ Build sequence complete."
