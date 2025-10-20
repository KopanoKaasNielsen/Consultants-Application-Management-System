#!/usr/bin/env python3
import os, sys, subprocess, re
from datetime import datetime
from openai import OpenAI

client = OpenAI()

BASE_DIR = os.path.expanduser("~/CAMS/consultant_app")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def run_cmd(cmd):
    """Run a command locally and capture stdout + stderr."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout + result.stderr
    except Exception as e:
        return f"⚠️  Error running command: {e}"

def extract_command(plan_text):
    """Find first shell command in GPT output."""
    code_block = re.findall(r"```(?:bash|shell)?\s*(.*?)```", plan_text, re.S)
    if code_block:
        return code_block[0].strip()
    for line in plan_text.splitlines():
        if line.strip().startswith("$ "):
            return line.strip().lstrip("$ ").strip()
        if line.strip().startswith(("git ", "pytest", "python", "ls", "echo")):
            return line.strip()
    return None

def codex_task(prompt):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    outfile = os.path.join(RESULTS_DIR, f"codex_run_{timestamp}.txt")

    print(f"🧠 Sending task to GPT-5 Codex...")
    try:
        response = client.responses.create(
            model="gpt-5",
            input=(
                "You are Codex, a Linux shell automation assistant.\n"
                "When given a task, respond with a command plan and an executable shell command.\n"
                "Use real Bash commands that can run in Ubuntu.\n\n"
                f"Task: {prompt}"
            ),
        )
        plan = getattr(response, "output_text", None)
        if not plan:
            plan = response.output[0].content[0].text
    except Exception as e:
        plan = f"⚠️ GPT-5 failed to plan: {e}"

    cmd = extract_command(plan)
    if not cmd:
        cmd = "(no command generated)"
        output = "(no command executed)"
    else:
        print(f"⚙️ Running: {cmd}")
        output = run_cmd(cmd)

    with open(outfile, "w") as f:
        f.write(f"🧠 Codex Plan:\n{plan}\n\n⚙️  Command:\n{cmd}\n\n📄 Output:\n{output}\n")

    print(f"✅ Result saved to: {outfile}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❗Usage: codex_agent.py '<instruction>'")
        sys.exit(1)
    codex_task(sys.argv[1])
