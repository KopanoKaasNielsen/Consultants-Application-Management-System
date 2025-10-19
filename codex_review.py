#!/usr/bin/env python3
import sys, os
from datetime import datetime
from openai import OpenAI

client = OpenAI()

if len(sys.argv) < 2:
    print("❗Usage: codex_review.py <PR_URL>")
    sys.exit(1)

pr_url = sys.argv[1]
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
outdir = os.path.expanduser("~/CAMS/consultant_app/reviews")
os.makedirs(outdir, exist_ok=True)
outfile = os.path.join(outdir, f"review-{timestamp}.md")

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
except Exception as e:
    review = f"⚠️ GPT-5 review failed: {e}"

with open(outfile, "w") as f:
    f.write(review or "⚠️ No review text returned.")

print(f"✅ Review complete — saved to {outfile}")
os.system(f"code {outfile}")

