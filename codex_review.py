#!/usr/bin/env python3
"""
codex_review.py — use GPT-5 to review Django code or GitHub PRs.

Usage examples:
    python codex_review.py apps/consultants/views.py
    python codex_review.py https://github.com/KopanoKaasNielsen/Consultants-Application-Management-System/pull/51
"""

import sys
import requests
from openai import OpenAI

client = OpenAI()

def review_text(content: str) -> str:
    """Send text or diff to GPT-5 for analysis."""
    response = client.responses.create(
        model="gpt-5",
        input=f"You are a senior Django code reviewer. Provide a clear, structured review with improvement suggestions:\n\n{content}"
    )
    # Works across SDK 2.5–2.7+
    try:
        return response.output[0].content[0].text
    except Exception:
        return getattr(response, "output_text", str(response))


def main():
    if len(sys.argv) < 2:
        print("Usage: python codex_review.py <PR_URL or file path>")
        sys.exit(1)

    target = sys.argv[1]

    # Determine if reviewing a GitHub PR or a local file
    if target.startswith("http"):
        print("🔍 Fetching PR diff from GitHub...")
        pr_api = (
            target.replace("github.com", "api.github.com/repos")
            .replace("/pull/", "/pulls/")
        )
        diff = requests.get(
            pr_api, headers={"Accept": "application/vnd.github.v3.diff"}
        ).text
        print("✅ PR diff fetched, sending to GPT-5...\n")
        review = review_text(diff)
    else:
        print(f"🔍 Reading local file: {target}")
        with open(target, "r") as f:
            content = f.read()
        review = review_text(content)

    print("\n🧠 GPT-5 Review Output:\n")
    print(review)


if __name__ == "__main__":
    main()
