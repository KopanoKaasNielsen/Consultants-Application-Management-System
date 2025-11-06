#!/usr/bin/env bash
# Synchronize a Neon connection string into a Render service environment variable.
#
# Usage examples:
#   RENDER_API_KEY=... RENDER_SERVICE_ID=... \
#   NEON_CONNECTION_STRING=postgresql://... \
#   ./scripts/configure_render_neon.sh --env-var DATABASE_URL --deploy
#
#   cat .neon_connection_string | RENDER_API_KEY=... RENDER_SERVICE_ID=... \
#     ./scripts/configure_render_neon.sh --env-var DATABASE_URL --deploy

set -euo pipefail

usage() {
  cat <<USAGE
Usage: configure_render_neon.sh [--connection-string <value>] [--env-var <name>] [--deploy]

Reads a Neon PostgreSQL connection string (from --connection-string or STDIN) and writes it to the
specified Render environment variable. Optionally triggers a new deploy.

Required environment variables:
  RENDER_API_KEY     Render API token with write access to the service
  RENDER_SERVICE_ID  Render service identifier (UUID)

Options:
  --connection-string <value>  Neon connection string to apply
  --env-var <name>             Render environment variable name to update (default: DATABASE_URL)
  --deploy                     Trigger a deploy after updating the variable
  -h, --help                   Show this message
USAGE
}

RENDER_API_KEY="${RENDER_API_KEY:-}"
RENDER_SERVICE_ID="${RENDER_SERVICE_ID:-}"

if [[ -z "$RENDER_API_KEY" || -z "$RENDER_SERVICE_ID" ]]; then
  echo "RENDER_API_KEY and RENDER_SERVICE_ID must be set in the environment." >&2
  usage
  exit 1
fi

connection_string=""
env_var_name="DATABASE_URL"
trigger_deploy="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --connection-string)
      shift
      connection_string="${1:-}"
      if [[ -z "$connection_string" ]]; then
        echo "--connection-string requires a value" >&2
        exit 1
      fi
      ;;
    --env-var)
      shift
      env_var_name="${1:-}"
      if [[ -z "$env_var_name" ]]; then
        echo "--env-var requires a value" >&2
        exit 1
      fi
      ;;
    --deploy)
      trigger_deploy="true"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift || true
done

if [[ -z "$connection_string" ]]; then
  if [[ -t 0 ]]; then
    echo "No connection string provided. Use --connection-string or pipe the value via STDIN." >&2
    exit 1
  fi
  connection_string="$(cat -)"
fi

connection_string="${connection_string//$'\r'/}" # strip carriage returns
connection_string="$(echo -n "$connection_string" | awk '{$1=$1;print}')"

if [[ -z "$connection_string" ]]; then
  echo "Connection string is empty after processing." >&2
  exit 1
fi

echo "Updating Render environment variable '$env_var_name' for service $RENDER_SERVICE_ID..."

payload=$(jq -cn --arg key "$env_var_name" --arg value "$connection_string" '[{"key":$key,"value":$value,"type":"SECRET"}]')

response=$(curl -fsS -X PUT "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/env-vars" \
  -H "Authorization: Bearer ${RENDER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$payload")

echo "Environment variable updated. Response: $response"

if [[ "$trigger_deploy" == "true" ]]; then
  echo "Triggering deploy..."
  deploy_response=$(curl -fsS -X POST "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys" \
    -H "Authorization: Bearer ${RENDER_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{}')
  echo "Deploy triggered. Response: $deploy_response"
fi

echo "Done."
