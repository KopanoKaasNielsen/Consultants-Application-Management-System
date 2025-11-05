#!/usr/bin/env python3
"""Compare the local repository against a remote baseline using GPT assistance."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict

from openai import OpenAI

client = OpenAI()

BASE_DIR = Path(__file__).resolve().parent
REMOTE_REPO = "https://github.com/KopanoKaasNielsen/Consultants-Application-Management-System"

if len(sys.argv) > 1:
    REMOTE_REPO = sys.argv[1]

print(f"📦 Comparing local source with remote repo: {REMOTE_REPO}")


def collect_python_files(base_dir: Path) -> Dict[str, str]:
    collected: Dict[str, str] = {}
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [
            d
            for d in dirs
            if d not in ("venv", "__pycache__", "results", "reviews", ".git")
        ]
        for filename in files:
            if filename.endswith(".py"):
                path = Path(root) / filename
                rel = path.relative_to(base_dir)
                try:
                    collected[str(rel)] = path.read_text(encoding="utf-8")
                except Exception:
                    pass
    return collected


def clone_remote_repo(repo_url: str) -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="codex_remote_"))
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(tmp_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return tmp_dir


# --- Step 1: Gather local files ---
local_files = collect_python_files(BASE_DIR)
print(f"✅ Local files collected: {len(local_files)}")

# --- Step 2: Gather remote files ---
remote_dir = clone_remote_repo(REMOTE_REPO)
remote_files = collect_python_files(remote_dir)
print(f"✅ Remote files collected: {len(remote_files)}")

# --- Step 3: Compare files ---
diff_summary = []
changed_files = 0
new_files = 0
missing_files = 0

for rel, content in local_files.items():
    if rel not in remote_files:
        new_files += 1
        diff_summary.append(f"🟢 New local file (not in remote): {rel}")
        continue
    if content != remote_files[rel]:
        changed_files += 1
        diff_summary.append(f"🟡 Modified file: {rel}")

for rel in remote_files:
    if rel not in local_files:
        missing_files += 1
        diff_summary.append(f"🔴 File missing locally (exists in remote): {rel}")

summary_text = (
    f"### Comparison Summary\n"
    f"- Local files: {len(local_files)}\n"
    f"- Remote files: {len(remote_files)}\n"
    f"- New local files: {new_files}\n"
    f"- Missing local files: {missing_files}\n"
    f"- Modified files: {changed_files}\n\n"
)

diff_summary_text = "\n".join(diff_summary[:100])

# --- Step 4: Get git status info ---
git_status = subprocess.getoutput(f"cd {BASE_DIR} && git status -sb")
uncommitted = subprocess.getoutput(f"cd {BASE_DIR} && git diff --stat")
unpushed = subprocess.getoutput(f"cd {BASE_DIR} && git cherry -v")

# --- Step 5: Ask GPT-5 for holistic evaluation ---
prompt = f"""
You are a senior Django code auditor.
Compare the local and remote repositories and give a full evaluation.

### Repository
Remote: {REMOTE_REPO}
Local directory: {BASE_DIR}

### Git Status
{git_status}

### Uncommitted Changes
{uncommitted}

### Unpushed Commits
{unpushed}

{summary_text}

### File Differences
{diff_summary_text}

Provide:
1. **Summary of differences**
2. **Potential risks or outdated files**
3. **Recommendations to sync safely**
4. **Overall evaluation of code quality and consistency**
"""

print("🧠 Sending comparison summary to GPT-5...")
response = client.responses.create(model="gpt-5", input=prompt)

try:
    report = response.output[0].content[0].text
except Exception:
    report = getattr(response, "output_text", str(response))

# --- Step 6: Save evaluation report ---
output_dir = BASE_DIR / "results" / "evaluations"
output_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = output_dir / f"codex_diff_eval_{timestamp}.md"

filename.write_text(report, encoding="utf-8")

print(f"✅ Evaluation complete.\n📄 Report saved to: {filename}")

# Clean up temporary clone
shutil.rmtree(remote_dir, ignore_errors=True)
