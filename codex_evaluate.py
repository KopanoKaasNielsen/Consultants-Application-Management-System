#!/usr/bin/env python3
import os, sys, subprocess, tempfile, shutil
from datetime import datetime
from openai import OpenAI

client = OpenAI()

# --- Collect local Python source files ---
def gather_local_source(base_dir):
    collected = []
    for root, dirs, files in os.walk(base_dir):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ("venv", "__pycache__", "results", "reviews", ".git")]
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    with open(path, "r") as file:
                        content = file.read()
                        collected.append(f"# {path}\n{content}\n\n")
                except Exception as e:
                    print(f"⚠️  Skipping {path}: {e}")
    return "\n".join(collected)

def fetch_remote_summary(repo_url):
    try:
        print(f"🔍 Fetching remote repo summary for {repo_url}...")
        output = subprocess.getoutput(f"git ls-remote {repo_url} HEAD")
        branches = subprocess.getoutput(f"git ls-remote --heads {repo_url}")
        return f"HEAD info:\n{output}\n\nBranches:\n{branches}"
    except Exception as e:
        return f"Error fetching remote repo info: {e}"

if len(sys.argv) > 1:
    repo_url = sys.argv[1]
else:
    repo_url = "https://github.com/KopanoKaasNielsen/Consultants-Application-Management-System"

base_dir = os.path.expanduser("~/CAMS/consultant_app")

print("📦 Gathering local source code (this may take a moment)...")
local_code = gather_local_source(base_dir)
print("✅ Local source collected.")

remote_info = fetch_remote_summary(repo_url)

# --- Prepare GPT-5 prompt ---
prompt = f"""
You are a senior Django software architect.

Evaluate both the local source code (below) and the structure of the remote repo at {repo_url}.
Provide a holistic technical review with sections:
1. **Architecture & Design**
2. **Code Quality & Patterns**
3. **Security & Config**
4. **Tests & Coverage**
5. **Deployment Readiness**
6. **Recommendations (High priority / Medium / Low)**

### Local Source Snapshot
{local_code[:30000]}  # Limit for safety (30k chars)

### Remote Repository Info
{remote_info}
"""

print("🧠 Sending to GPT-5 Codex for evaluation...")
response = client.responses.create(
    model="gpt-5",
    input=prompt
)

try:
    report = response.output[0].content[0].text
except Exception:
    report = getattr(response, "output_text", str(response))

# --- Save to results folder ---
output_dir = os.path.join(base_dir, "results", "evaluations")
os.makedirs(output_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = os.path.join(output_dir, f"codex_evaluation_{timestamp}.md")

with open(filename, "w") as f:
    f.write(report)

print(f"✅ Evaluation complete. Report saved to: {filename}")
