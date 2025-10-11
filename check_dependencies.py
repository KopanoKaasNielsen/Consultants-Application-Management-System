#!/usr/bin/env python3
import subprocess, sys

# List all essential packages for CAMS
required = [
    "django", "djangorestframework", "django-crontab", "channels",
    "daphne", "openai", "psycopg2-binary", "gunicorn"
]

for pkg in required:
    try:
        __import__(pkg.split('-')[0])
        print(f"✅ {pkg} is already installed.")
    except ImportError:
        print(f"📦 Installing missing package: {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

print("🎯 All dependencies checked and installed.")
