#!/usr/bin/env python3
import os, sys
from datetime import datetime
from openai import OpenAI

client = OpenAI()

if len(sys.argv) < 2:
    print("❗Usage: codex_fix.py <PR_URL>")
    sys.exit(1)

pr_url = sys.argv[1]
base_dir = os.path.expanduser("~/CAMS/consultant_app")
out_dir = os.path.join(base_dir, "results", "fixes")
os.makedirs(out_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
outfile = os.path.join(out_dir, f"codex_fix_{timestamp}.md")

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
except Exception as e:
    output = f"⚠️ Fix generation failed: {e}"

with open(outfile, "w") as f:
    f.write(output or "⚠️ No fix text returned.")

print(f"✅ Fix suggestions saved to {outfile}")
