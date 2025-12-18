#!/usr/bin/env bash

set -euo pipefail

echo "[devcontainer] Proxy env:"
echo "  HTTP_PROXY=${HTTP_PROXY:-}"
echo "  HTTPS_PROXY=${HTTPS_PROXY:-}"
echo "  NO_PROXY=${NO_PROXY:-}"

# If you are behind a corporate proxy that MITMs TLS, place your CA cert here:
#   .devcontainer/certs/devcontainer-extra-ca.crt
#
# This file is intentionally gitignored (see .devcontainer/certs/.gitignore).
EXTRA_CA_SOURCE="${PWD}/.devcontainer/certs/devcontainer-extra-ca.crt"
EXTRA_CA_TARGET="/usr/local/share/ca-certificates/devcontainer-extra-ca.crt"

if [[ -f "${EXTRA_CA_SOURCE}" ]]; then
  echo "[devcontainer] Installing extra CA certificate into system trust store..."

  if ! command -v update-ca-certificates >/dev/null 2>&1; then
    echo "[devcontainer] update-ca-certificates not found; attempting to install ca-certificates..."
    if command -v sudo >/dev/null 2>&1; then
      sudo apt-get update -y
      sudo apt-get install -y ca-certificates
    elif [[ "$(id -u)" == "0" ]]; then
      apt-get update -y
      apt-get install -y ca-certificates
    else
      echo "[devcontainer] No sudo and not root; cannot install ca-certificates automatically."
      exit 0
    fi
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo install -m 0644 "${EXTRA_CA_SOURCE}" "${EXTRA_CA_TARGET}"
    sudo update-ca-certificates
  elif [[ "$(id -u)" == "0" ]]; then
    install -m 0644 "${EXTRA_CA_SOURCE}" "${EXTRA_CA_TARGET}"
    update-ca-certificates
  else
    echo "[devcontainer] No sudo and not root; cannot update system trust store."
    exit 0
  fi
  echo "[devcontainer] Extra CA installed at ${EXTRA_CA_TARGET}"
else
  echo "[devcontainer] No extra CA file found at ${EXTRA_CA_SOURCE} (skipping)."
fi

echo "[devcontainer] Proxy/CA setup complete."
