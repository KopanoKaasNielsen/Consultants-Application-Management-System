#!/usr/bin/env python3
"""Produce a GPT-5 Codex review for a given pull request URL."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI

client = OpenAI()

if len(sys.argv) < 2:
    print("❗Usage: codex_review.py <PR_URL>")
    sys.exit(1)

pr_url = sys.argv[1]
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
outdir = Path(__file__).resolve().parent / "reviews"
outdir.mkdir(parents=True, exist_ok=True)
outfile = outdir / f"review-{timestamp}.md"

prompt = f"""
You are GPT-5 Codex, a senior Django reviewer.
Analyze this pull request and summarize its quality, logic, and potential issues.

PR: {pr_url}

Provide:
1. Overall purpose and scope
2. Security or logic flaws
3. Code style or redundancy
4. Readiness for merge
"""

print(f"🧠 Reviewing PR: {pr_url}")

try:
    response = client.responses.create(model="gpt-5", input=prompt)
    review = getattr(response, "output_text", None)
    if not review:
        try:
            review = response.output[0].content[0].text
        except Exception:
            review = str(response)
except Exception as exc:  # pragma: no cover - defensive logging
    review = f"⚠️ GPT-5 review failed: {exc}"

outfile.write_text(review or "⚠️ No review text returned.", encoding="utf-8")

print(f"✅ Review complete — saved to {outfile}")

code_cmd = shutil.which("code")
if code_cmd:
    try:
        subprocess.run(
            [code_cmd, str(outfile)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
else:
    print("ℹ️ VS Code CLI not available; review left on disk.")
