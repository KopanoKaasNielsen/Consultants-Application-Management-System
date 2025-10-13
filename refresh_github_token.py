#!/usr/bin/env python3
import os
import requests
import subprocess
from pathlib import Path

# === CONFIG ===
GITHUB_API = "https://api.github.com/user"
TOKEN_ENV_VAR = "GITHUB_TOKEN"
TOKEN_FILE = Path.home() / ".github_token"

def get_token():
    """Try to retrieve GitHub token from environment or local file."""
    token = os.getenv(TOKEN_ENV_VAR)
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        os.environ[TOKEN_ENV_VAR] = token
    return token

def validate_token(token):
    """Check if GitHub token is valid by hitting the /user endpoint."""
    try:
        headers = {"Authorization": f"token {token}"}
        response = requests.get(GITHUB_API, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"✅ Token is valid for user: {response.json()['login']}")
            return True
        else:
            print(f"⚠️ Invalid token (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error validating token: {e}")
        return False

def save_token(new_token):
    """Save new token to local file and export it for future sessions."""
    TOKEN_FILE.write_text(new_token.strip())
    os.environ[TOKEN_ENV_VAR] = new_token.strip()
    print(f"✅ New token saved to {TOKEN_FILE}")

def update_git_credentials(token):
    """Update Git global credentials for HTTPS authentication."""
    subprocess.run(["git", "config", "--global", "credential.helper", "store"], check=False)
    # Simulate git credential storage
    cred_data = f"https://{token}:x-oauth-basic@github.com\n"
    cred_path = Path.home() / ".git-credentials"
    cred_path.write_text(cred_data)
    print(f"✅ Git credentials updated at {cred_path}")

def main():
    print("🔍 Checking your GitHub token...")
    token = get_token()

    if not token or not validate_token(token):
        print("\n🚨 Your token is missing or invalid.")
        new_token = input("👉 Paste your new GitHub Personal Access Token (PAT): ").strip()
        if not new_token:
            print("❌ No token entered. Aborting.")
            return
        save_token(new_token)
        if validate_token(new_token):
            update_git_credentials(new_token)
            print("🎯 Token successfully refreshed and applied.")
        else:
            print("⚠️ The new token is still invalid. Please check scopes on GitHub.")
    else:
        print("🎉 Your GitHub token is active and ready to use.")

if __name__ == "__main__":
    main()
