#!/usr/bin/env python3
import os, sys, subprocess
from datetime import datetime
from openai import OpenAI

client = OpenAI()

BASE_DIR = os.path.expanduser("~/CAMS/consultant_app")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def run_cmd(cmd):
    """Execute a shell command and capture its output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=False
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"⚠️  Command failed: {e}"

def codex_task(prompt):
    """Send the user’s natural-language prompt to GPT-5 Codex and run what it plans."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = os.path.join(RESULTS_DIR, f"codex_run_{timestamp}.txt")

    try:
        response = client.responses.create(
            model="gpt-5",
            input=f"You are Codex, a shell-automation agent.\n"
                  f"User task: {prompt}\n"
                  "Decide what command to run. "
                  "Respond ONLY with:\n"
                  "1️⃣ The command you’ll run.\n"
                  "2️⃣ The purpose.\n"
                  "3️⃣ Then execute it and return the output."
        )
        plan = getattr(response, "output_text", None)
        if not plan:
            plan = response.output[0].content[0].text
    except Exception as e:
        plan = f"⚠️  GPT-5 planning failed: {e}"

    cmd = None
    # Extract a command from GPT-5 output (between code fences or after '$')
    for line in plan.splitlines():
        if line.strip().startswith("```"):
            continue
        if line.strip().startswith("$ "):
            cmd = line.strip().lstrip("$ ").strip()
            break
        if line.strip().startswith("python") or line.strip().startswith("pytest") or line.strip().startswith("git"):
            cmd = line.strip()
            break

    output = run_cmd(cmd) if cmd else "(no command generated)"

    with open(out_file, "w") as f:
        f.write(f"🧠 Codex Plan:\n{plan}\n\n⚙️  Command:\n{cmd}\n\n📄 Output:\n{output}\n")

    print(f"✅ Result saved to: {out_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❗Usage: codex_agent.py '<instruction>'")
        sys.exit(1)
    codex_task(sys.argv[1])
