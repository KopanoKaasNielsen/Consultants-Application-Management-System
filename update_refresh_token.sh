#!/bin/bash
# 🔄 Auto-update the refresh_github_token.py script

TARGET="refresh_github_token.py"

echo "📦 Updating $TARGET ..."

cat <<'PYCODE' > $TARGET
#!/usr/bin/env python3
import os
import requests
import subprocess
from pathlib import Path

GITHUB_API_USER = "https://api.github.com/user"
TOKEN_ENV_VAR = "GITHUB_TOKEN"
TOKEN_FILE = Path.home() / ".github_token"
REQUIRED_SCOPES = {"repo", "read:org", "workflow"}

def get_token():
    token = os.getenv(TOKEN_ENV_VAR)
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        os.environ[TOKEN_ENV_VAR] = token
    return token

def validate_token(token):
    try:
        headers = {"Authorization": f"token {token}"}
        resp = requests.get(GITHUB_API_USER, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ Token invalid or expired (HTTP {resp.status_code}).")
            return None, set()
        scopes_header = resp.headers.get("x-oauth-scopes", "")
        scopes = {s.strip() for s in scopes_header.split(",") if s.strip()}
        username = resp.json().get("login", "unknown")
        print(f"✅ Token is valid for user: {username}")
        return username, scopes
    except Exception as e:
        print(f"❌ Error validating token: {e}")
        return None, set()

def detect_missing_scopes(scopes):
    missing = REQUIRED_SCOPES - scopes
    if missing:
        print("\n🚨 Missing required scopes:")
        for s in missing:
            print(f"   - {s}")
        print("""
🧭 To fix this:
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name it e.g. CAMS-AutoDev
4. Check the following scopes:
   ✅ repo
   ✅ read:org
   ✅ workflow
5. Generate token and paste it below.
""")
    return missing

def save_token(token):
    TOKEN_FILE.write_text(token.strip())
    os.environ[TOKEN_ENV_VAR] = token.strip()
    print(f"✅ Token saved to {TOKEN_FILE}")

def update_git_credentials(token):
    subprocess.run(["git", "config", "--global", "credential.helper", "store"], check=False)
    cred_path = Path.home() / ".git-credentials"
    cred_path.write_text(f"https://{token}:x-oauth-basic@github.com\n")
    print(f"✅ Git credentials updated at {cred_path}")

def main():
    print("🔍 Checking your GitHub token...")
    token = get_token()
    username, scopes = (None, set())
    if token:
        username, scopes = validate_token(token)
    if not token or not username:
        print("\n🚨 Token missing or invalid.")
        new_token = input("👉 Paste your new GitHub Personal Access Token (PAT): ").strip()
        if not new_token:
            print("❌ No token entered. Aborting.")
            return
        save_token(new_token)
        username, scopes = validate_token(new_token)
    missing = detect_missing_scopes(scopes)
    if missing:
        print("⚠️ Please regenerate your token with the scopes above.")
        return
    if username:
        update_git_credentials(token)
        print(f"🎯 Token valid and all required scopes present for user: {username}")

if __name__ == "__main__":
    main()
PYCODE

chmod +x $TARGET
echo "✅ $TARGET updated successfully."
