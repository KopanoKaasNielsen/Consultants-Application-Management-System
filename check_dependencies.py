#!/usr/bin/env python3
import subprocess, sys

# List all essential packages for CAMS
required = [
    ("django", "django"),
    ("djangorestframework", "rest_framework"),
    ("django-crontab", "django_crontab"),
    ("channels", "channels"),
    ("daphne", "daphne"),
    ("openai", "openai"),
    ("psycopg2-binary", "psycopg2"),
    ("gunicorn", "gunicorn"),
]

missing: list[str] = []
for pkg, import_name in required:
    try:
        __import__(import_name)
        print(f"✅ {pkg} is already installed.")
    except ImportError:
        missing.append(pkg)
        print(f"❌ Missing: {pkg}")

auto_install = __import__("os").environ.get("CAMS_AUTO_INSTALL", "0") == "1"
if missing and auto_install:
    for pkg in missing:
        print(f"📦 Installing missing package: {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
elif missing:
    print(
        "ℹ️ Missing dependencies detected. Install with: python -m pip install -r requirements.txt "
        "(or set CAMS_AUTO_INSTALL=1 to auto-install during devcontainer create)."
    )

print("🎯 All dependencies checked and installed.")
