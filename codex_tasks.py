#!/usr/bin/env python3
"""Utility helpers for running the Codex automation task catalogue.

Historically the script assumed the repository was checked out to
``~/CAMS/consultant_app`` which breaks on staging environments where the code
lives elsewhere.  Paths are now resolved relative to this file so the tooling is
portable regardless of where the repo is cloned.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import yaml

BASE_DIR = Path(__file__).resolve().parent
TASK_FILE = BASE_DIR / "codex_ci_tasks.yml"
LOG_DIR = BASE_DIR / "results" / "tasks"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    """Print a timestamped log line."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def create_task(args: Dict[str, str]) -> None:
    """Create a new Codex task entry and append it to ``codex_ci_tasks.yml``."""
    if not TASK_FILE.exists():
        TASK_FILE.write_text("tasks:\n", encoding="utf-8")

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

    with TASK_FILE.open("a", encoding="utf-8") as handle:
        handle.write(
            f"""
  {name}:
    description: "{desc}"
    command: |
      codex custom "You are GPT-5 Codex. Task type: {task_type}.
      Goal: {goal}.
      Acceptance criteria: {criteria}.
      Component: {component}.
      Fix strategy: {fix}.
      Perform the requested review or fix and output result."
"""
        )

    log(f"✅ Task '{name}' created and saved to {TASK_FILE}.")


def load_tasks() -> Dict[str, Dict[str, str]]:
    """Return the task mapping from ``codex_ci_tasks.yml``."""
    if not TASK_FILE.exists():
        log(f"❗ Task file not found: {TASK_FILE}")
        sys.exit(1)

    with TASK_FILE.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return data.get("tasks", {})


def run_task(task_name: str) -> None:
    """Execute a named task and stream its output to stdout and a log file."""
    tasks = load_tasks()
    if task_name not in tasks:
        log(f"❌ Unknown task: {task_name}")
        log("🧾 Available tasks:")
        for name in tasks:
            print(f"  - {name}")
        sys.exit(1)

    task = tasks[task_name]
    desc = task.get("description", "")
    command = task.get("command", "").strip()

    log(f"🚀 Running Codex task: {task_name}")
    if desc:
        log(f"📘 {desc}")

    logfile = LOG_DIR / f"{task_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

    try:
        with logfile.open("w", encoding="utf-8") as logf:
            logf.write(f"# Task: {task_name}\n# Description: {desc}\n\n")
            logf.write(f"$ {command}\n\n")
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
            )
            if process.stdout is None:
                raise RuntimeError("Failed to capture task output stream")
            for line in iter(process.stdout.readline, b""):
                decoded = line.decode()
                sys.stdout.write(decoded)
                logf.write(decoded)
        log(f"✅ Task '{task_name}' complete. Log saved to {logfile}")
    except Exception as exc:  # pragma: no cover - defensive logging
        log(f"❌ Error running task: {exc}")


def run_all_tasks() -> None:
    tasks = load_tasks()
    if not tasks:
        log("❗No tasks defined in codex_ci_tasks.yml")
        sys.exit(1)

    log("🧠 Running all Codex tasks sequentially...")
    for name in tasks:
        log(f"\n--- 🧩 Starting task: {name} ---")
        run_task(name)
    log("✅ All Codex tasks completed successfully.")


def parse_create_args(argv: list[str]) -> Dict[str, str]:
    arg_pairs: Dict[str, str] = {}
    key: str | None = None
    for item in argv:
        if item.startswith("--"):
            key = item
            arg_pairs[key] = ""
        elif key:
            arg_pairs[key] = (arg_pairs[key] + " " + item).strip()
    return arg_pairs


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        log("❗Usage: codex task <task-name> | codex task all | codex task create ...")
        return 1

    cmd = argv[1]

    if cmd == "create":
        create_task(parse_create_args(argv[2:]))
        return 0

    if cmd == "all":
        run_all_tasks()
        return 0

    run_task(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
