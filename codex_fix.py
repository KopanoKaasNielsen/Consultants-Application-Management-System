#!/usr/bin/env python3
"""Generate GPT-5 Codex fix suggestions for a pull request."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI

client = OpenAI()

if len(sys.argv) < 2:
    print("❗Usage: codex_fix.py <PR_URL>")
    sys.exit(1)

pr_url = sys.argv[1]
base_dir = Path(__file__).resolve().parent
out_dir = base_dir / "results" / "fixes"
out_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
outfile = out_dir / f"codex_fix_{timestamp}.md"

prompt = f"""
You are GPT-5 Codex.
Analyze PR: {pr_url}

1. Identify issues based on Django best practices.
2. Suggest or generate corrected code snippets.
3. Focus on safe automation-compatible changes (e.g., dependency pins, CI scripts, doc updates).
4. Output actionable patch instructions or shell steps.
"""

print(f"🧩 Applying GPT-5 Codex fixes for {pr_url} ...")

try:
    response = client.responses.create(model="gpt-5", input=prompt)
    output = getattr(response, "output_text", None)
    if not output:
        try:
            output = response.output[0].content[0].text
        except Exception:
            output = str(response)
except Exception as exc:  # pragma: no cover - defensive logging
    output = f"⚠️ Fix generation failed: {exc}"

outfile.write_text(output or "⚠️ No fix text returned.", encoding="utf-8")

print(f"✅ Fix suggestions saved to {outfile}")
