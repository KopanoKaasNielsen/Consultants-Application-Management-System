#!/usr/bin/env bash

set -u

echo "[devcontainer] Post-create starting..."
echo "[devcontainer] Working directory: $(pwd)"
echo "[devcontainer] CAMS_AUTO_INSTALL=${CAMS_AUTO_INSTALL:-0}"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

echo "[devcontainer] Configuring proxy/CA trust (best effort)..."
bash .devcontainer/setup-proxy-ca.sh || true

if [[ "${CAMS_AUTO_INSTALL:-0}" == "1" ]]; then
  echo "[devcontainer] Installing Python dependencies from requirements.txt (best effort)..."
  python -m pip install --upgrade pip || true
  python -m pip install -r requirements.txt || true

  if [[ -f "frontend/package-lock.json" ]]; then
    echo "[devcontainer] Installing frontend dependencies via npm ci (best effort)..."
    (cd frontend && npm ci) || true
  fi
else
  echo "[devcontainer] Skipping pip/npm installs (network may be restricted)."
  echo "[devcontainer] To enable auto-install on create, set CAMS_AUTO_INSTALL=1 in your devcontainer env."
fi

echo "[devcontainer] Checking key Python imports..."
python3 check_dependencies.py || true

echo "[devcontainer] Post-create complete."
