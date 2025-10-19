#!/usr/bin/env python3
"""
codex_tasks.py — task loader for Codex CI automation
Usage:
    codex task <task-name>
"""
import os
import sys
import yaml
import subprocess
from datetime import datetime

BASE_DIR = os.path.expanduser("~/CAMS/consultant_app")
TASK_FILE = os.path.join(BASE_DIR, "codex_ci_tasks.yml")
LOG_DIR = os.path.join(BASE_DIR, "results", "tasks")
os.makedirs(LOG_DIR, exist_ok=True)

def create_task(args):
    """
    Create a new Codex task entry dynamically and save to codex_ci_tasks.yml
    """
    if not os.path.exists(TASK_FILE):
        with open(TASK_FILE, "w") as f:
            f.write("tasks:\n")

    name = args.get("--name")
    desc = args.get("--description", "")
    goal = args.get("--goal", "")
    criteria = args.get("--acceptance-criteria", "")
    component = args.get("--component", "")
    task_type = args.get("--type", "review")
    fix = args.get("--fix", "manual")

    if not name:
        log("❗Missing required parameter: --name")
        sys.exit(1)

    with open(TASK_FILE, "a") as f:
        f.write(f"""
  {name}:
    description: "{desc}"
    command: |
      codex custom "You are GPT-5 Codex. Task type: {task_type}.
      Goal: {goal}.
      Acceptance criteria: {criteria}.
      Component: {component}.
      Fix strategy: {fix}.
      Perform the requested review or fix and output result."
""")

    log(f"✅ Task '{name}' created and saved to codex_ci_tasks.yml.")



def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def load_tasks():
    if not os.path.exists(TASK_FILE):
        log(f"❗ Task file not found: {TASK_FILE}")
        sys.exit(1)
    with open(TASK_FILE, "r") as f:
        data = yaml.safe_load(f)
    return data.get("tasks", {})

def run_task(task_name):
    tasks = load_tasks()
    if task_name not in tasks:
        log(f"❌ Unknown task: {task_name}")
        log("🧾 Available tasks:")
        for name in tasks.keys():
            print(f"  - {name}")
        sys.exit(1)

    task = tasks[task_name]
    desc = task.get("description", "")
    command = task.get("command", "").strip()

    log(f"🚀 Running Codex task: {task_name}")
    if desc:
        log(f"📘 {desc}")

    # Create a log file
    logfile = os.path.join(LOG_DIR, f"{task_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

    try:
        with open(logfile, "w") as logf:
            logf.write(f"# Task: {task_name}\n# Description: {desc}\n\n")
            logf.write(f"$ {command}\n\n")
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in iter(process.stdout.readline, b""):
                sys.stdout.write(line.decode())
                logf.write(line.decode())
        log(f"✅ Task '{task_name}' complete. Log saved to {logfile}")
    except Exception as e:
        log(f"❌ Error running task: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        log("❗Usage: codex task <task-name>")
        sys.exit(1)
    run_task(sys.argv[1])

if __name__ == "__main__":
    if len(sys.argv) < 2:
        log("❗Usage: codex task <task-name> | codex task all")
        sys.exit(1)

    arg = sys.argv[1]
    tasks = load_tasks()

    if arg == "all":
        log("🧠 Running all Codex tasks sequentially...")
        for name in tasks.keys():
            log(f"\n--- 🧩 Starting task: {name} ---")
            run_task(name)
        log("✅ All Codex tasks completed successfully.")
    else:
        run_task(arg)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        log("❗Usage: codex task <task-name> | codex task all | codex task create ...")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "create":
        # Convert args like --name "x" into a dictionary
        arg_pairs = {}
        key = None
        for item in sys.argv[2:]:
            if item.startswith("--"):
                key = item
                arg_pairs[key] = ""
            else:
                if key:
                    if arg_pairs[key]:
                        arg_pairs[key] += " " + item
                    else:
                        arg_pairs[key] = item
        create_task(arg_pairs)

    elif cmd == "all":
        tasks = load_tasks()
        log("🧠 Running all Codex tasks sequentially...")
        for name in tasks.keys():
            log(f"\n--- 🧩 Starting task: {name} ---")
            run_task(name)
        log("✅ All Codex tasks completed successfully.")

    else:
        run_task(cmd)
