#!/usr/bin/env python3
import os
import subprocess
import sys


def install_python_dependencies():
    requirements_path = os.path.join(os.getcwd(), "requirements.txt")
    if os.path.exists(requirements_path):
        print("🔍 Installing Python dependencies from requirements.txt...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
    else:
        print("⚠️ requirements.txt not found — skipping Python dependency installation.")


# === 1. Python dependencies ===
install_python_dependencies()

# === 2. Node.js / React dependencies ===
frontend_path = os.path.join(os.getcwd(), "frontend")
if os.path.exists(frontend_path):
    print("\n🔍 Checking Node.js dependencies...")
    try:
        subprocess.run(["npm", "install"], cwd=frontend_path, check=True)
        print("✅ Node.js dependencies installed.")
    except FileNotFoundError:
        print("⚠️ Node.js not found. Please install Node.js and npm manually.")
else:
    print("⚠️ Frontend folder not found — skipping npm install.")

# === 3. PostgreSQL connection check ===
print("\n🔍 Checking PostgreSQL connection...")
try:
    import psycopg2

    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "cams_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        connect_timeout=5,
    )
    conn.close()
    print("✅ PostgreSQL connection successful.")
except ImportError:
    print("⚠️ psycopg2 is not installed; skip database connectivity check.")
except Exception as e:
    print(f"⚠️ PostgreSQL connection failed: {e}")

# === 4. Django setup ===
print("\n⚙️ Applying Django migrations...")
try:
    subprocess.run(["python3", "manage.py", "makemigrations"], check=True)
    subprocess.run(["python3", "manage.py", "migrate"], check=True)
    print("✅ Django migrations applied successfully.")
except Exception as e:
    print(f"⚠️ Migration error: {e}")

print("\n🎯 Environment setup complete! CAMS is ready to run 🚀")
