#!/bin/bash
# ============================================================
#  Codex Mirror Sync Script
#  Mirrors this repo to a public read-only repository on push
#  Excludes sensitive files: .env, tokens, API keys, etc.
# ============================================================

# --- CONFIGURATION ------------------------------------------
MAIN_REMOTE="origin"
MIRROR_REMOTE="mirror"
MIRROR_URL="https://github.com/KopanoKaasNielsen/Consultants-Application-Management-System-Mirror.git"

# --- CHECK IF MIRROR EXISTS ---------------------------------
if ! git remote get-url "$MIRROR_REMOTE" &>/dev/null; then
    echo "⚙️  Adding mirror remote..."
    git remote add "$MIRROR_REMOTE" "$MIRROR_URL"
fi

# --- PREPARE SAFE MIRROR TEMP DIR ----------------------------
TMP_DIR=$(mktemp -d)
echo "📁 Preparing clean mirror in: $TMP_DIR"

git clone --mirror . "$TMP_DIR"

# --- REMOVE SENSITIVE FILES ----------------------------------
cd "$TMP_DIR" || exit 1
echo "🧹 Removing sensitive files and large assets..."
rm -f .env *.env *.pem *.key *.crt
rm -rf secrets/ tokens/ private_keys/ render.yaml

# --- FILTER TO KEEP IT LIGHT ---------------------------------
# Keep only necessary history (last 30 commits)
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git fetch --depth=30 "$MAIN_REMOTE"

# --- PUSH MIRROR ---------------------------------------------
echo "🚀 Pushing mirror to: $MIRROR_URL"
git push --mirror "$MIRROR_REMOTE"

# --- CLEANUP -------------------------------------------------
cd ..
rm -rf "$TMP_DIR"
echo "✅ Mirror sync complete."
