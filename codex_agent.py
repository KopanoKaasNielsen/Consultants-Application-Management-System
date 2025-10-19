#!/usr/bin/env python3
"""
codex_agent.py — Local automation powered by GPT-5-Codex.

Examples:
    python codex_agent.py "Run tests and fix simple lint errors."
    python codex_agent.py "Summarize the last 20 git commits."
"""

import os, subprocess, sys
from openai import OpenAI

client = OpenAI()

def run_local(cmd):
    """Execute a shell command and return its output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True
        )
        return result.stdout.strip() + "\n" + result.stderr.strip()
    except Exception as e:
        return f"Error executing command: {e}"

def codex_task(prompt):
    """Ask GPT-5-Codex what to do, run it, and print results."""
    system_prompt = (
        "You are a local DevOps assistant running inside a secure WSL shell. "
        "You can inspect files, run shell commands, and summarize outputs. "
        "Always explain what you're doing before running commands."
    )

    # Ask GPT-5-Codex for plan + commands
    plan = client.responses.create(
        model="gpt-5-codex",
        input=f"{system_prompt}\n\nTask:\n{prompt}"
    )

    try:
        text = plan.output[0].content[0].text
    except Exception:
        text = plan.output_text

    print("\n🧠 Codex Plan:\n", text)

    # Extract and execute any code fences like ```bash ... ```
    import re
    commands = re.findall(r"```bash(.*?)```", text, re.DOTALL)
    for cmd in commands:
        print(f"\n⚙️  Running: {cmd.strip()}")
        output = run_local(cmd.strip())
        print(f"\n📄 Output:\n{output}\n")
            # --- Save output to results folder ---
    # --- Save output to results folder (safe version) ---
    from datetime import datetime
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"codex_run_{timestamp}.txt"
    filepath = os.path.join(results_dir, filename)

    # Fallback if no commands were generated
    cmd_text = cmd.strip() if 'cmd' in locals() else "(no command generated)"

    with open(filepath, "w") as f:
        f.write(
            f"🧠 Codex Plan:\n{text}\n\n"
            f"⚙️  Command:\n{cmd_text}\n\n"
            f"📄 Output:\n{output if 'output' in locals() else '(no output)'}\n"
        )

    print(f"✅ Results saved to: {filepath}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python codex_agent.py \"<your instruction>\"")
        sys.exit(1)
    prompt = " ".join(sys.argv[1:])
    codex_task(prompt)
