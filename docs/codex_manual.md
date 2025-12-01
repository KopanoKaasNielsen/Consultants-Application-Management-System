# Codex Command Manual

The repository ships with a local `codex` command that mirrors the behaviour of
GitHub's Codex automation so the same workflows run reliably on developer
machines, CI, and staging environments. This manual explains how to install the
helper, run the available commands, and interpret their output.

> **What changed in this release?** The `codex review` command now compiles each
> Python file individually so syntax errors report precise filenames. Argument
> parsing has been tightened, and unit tests are available for quick regression
> checks.

## 1. Installation and prerequisites

1. **Python 3.9 or newer** — the CLI uses the system Python to compile the
   repository when running `codex review`.
2. **Git** — optional but recommended. When present, the command prints a
   concise status summary at the end of each run.
3. **Repository checkout** — clone or download the
   `Consultants-Application-Management-System` repo and open a shell at its
   root. All examples below assume commands are executed from this directory.

If you plan to run the Codex task catalogue you also need a writable
`codex/results/tasks/` directory. The CLI creates it automatically the first
time you execute a task, so no manual setup is required.

## 2. Command overview

The `codex` executable exposes two families of functionality:

| Command | Purpose |
| ------- | ------- |
| `codex review` | Run local repository checks and optional formatting fixes. |
| `python codex_tasks.py ...` | Manage and execute saved Codex automation tasks. |

> **Tip:** If you add the repository root to your `PATH`, you can invoke the
> helper by typing `codex` directly. Otherwise, call it via
> `python codex` or `./codex` from the repo root.

## 3. `codex review`

`codex review` provides a local safety net when the hosted Codex service is not
available. It scans Python files, optionally applies trailing whitespace fixes,
and compiles each file to bytecode to surface syntax errors before they hit CI.

### Syntax

```bash
codex review [--repo <path>] [--apply-fixes] [--no-compile]
```

### Options

- `--repo <path>` — Override the repository path. The default is the current
  working directory. The path is resolved before running any checks, so you can
  provide relative or absolute values.
- `--apply-fixes` — Enable safe auto-fixes. The CLI trims trailing whitespace
  and appends a newline at the end of each Python file it touches. Modified
  files are listed in the output.
- `--no-compile` — Skip the bytecode compilation step. Use this flag if you only
  need lint-style feedback or if the target directory is not a Python project.

### Quick start recipes

- **Run a hygiene pass with fixes:** `codex review --apply-fixes`
- **Check a different checkout:** `codex review --repo ../other-repo`
- **Skip compilation (non-Python project):** `codex review --no-compile`
- **Preview changes without touching files:** `codex review` (omit
  `--apply-fixes`)

### Output

A typical run prints:

1. **Repository and file statistics** — number of Python files and total lines.
2. **Fix summary** — which files changed when `--apply-fixes` is enabled.
3. **Compile results** — success/failure banner. When compilation fails, the
   output lists each file path and the associated syntax error.
4. **Git status** — the short status from `git status --short`. If Git is not
   installed, the command gracefully reports that the executable is unavailable.

The process exits with status code `0` when compilation succeeds (or is skipped)
and `1` when compilation fails. This makes it safe to wire the command into CI
pipelines.

## 4. Local validation

After updating the CLI, you can run the focused regression suite without
bootstrapping the full Django stack:

```bash
SKIP_DJANGO_SETUP=1 pytest tests/test_codex_cli.py
```

The `SKIP_DJANGO_SETUP` flag bypasses optional app imports so the tests execute
quickly on a vanilla Python environment.

## 5. Codex task catalogue (`codex_tasks.py`)

The repository also includes a lightweight task runner that stores Codex
instructions in `codex_ci_tasks.yml`. Tasks capture a reusable prompt or
workflow you can run locally with one command.

### 5.1 Listing and running tasks

Run a saved task by name:

```bash
python codex_tasks.py <task-name>
```

To execute every task sequentially, use:

```bash
python codex_tasks.py all
```

Each run streams the task's output to your terminal and writes a timestamped log
under `codex/results/tasks/`. This makes it easy to diff outputs across staging
runs or attach logs to support tickets.

If you reference an unknown task, the helper prints the list of available names
from `codex_ci_tasks.yml` so you can pick the right entry.

### 5.2 Creating new tasks

Use the `create` sub-command to append a task definition to the catalogue. Each
flag maps to a property in the generated YAML block.

```bash
python codex_tasks.py create \
  --name "security_audit" \
  --description "Run static security audit" \
  --goal "Inspect security-sensitive modules" \
  --acceptance-criteria "No HIGH alerts" \
  --component "backend" \
  --type "review" \
  --fix "manual"
```

The helper validates the required `--name` argument, scaffolds the
`codex_ci_tasks.yml` file when missing, and appends the formatted task block. The
resulting command is ready to run locally or in staging:

```yaml
  security_audit:
    description: "Run static security audit"
    command: |
      codex custom "You are GPT-5 Codex. Task type: review.
      Goal: Inspect security-sensitive modules.
      Acceptance criteria: No HIGH alerts.
      Component: backend.
      Fix strategy: manual.
      Perform the requested review or fix and output result."
```

### 5.3 Log locations and troubleshooting

- **Log directory:** `codex/results/tasks/`. Each file is named using the task
  and timestamp (for example, `security_audit_2024-05-01_12-30-00.log`).
- **Missing YAML file:** If `codex_ci_tasks.yml` does not exist, the helper
  creates a minimal shell when you run `create`. Running or listing tasks before
  the file exists exits with a helpful error message.
- **External commands:** Because tasks often wrap other CLIs, ensure any required
  tools are available on your `PATH` before running them locally or on staging.

## 6. Automation shell helper (`codex_ci_tasks.sh`)

For CI systems that prefer shell entry points, use the provided wrapper:

```bash
./codex_ci_tasks.sh <task-name>
```

The script resolves the Python interpreter automatically, changes into the repo
root, and executes `python codex_tasks.py <task-name>`. When you run it with
`all`, it cascades through the entire catalogue just like the Python module.
Because the script only relies on relative paths, it works the same way in
staging checkouts.

## 7. Recommended workflows

- **Quick hygiene check:** `codex review --apply-fixes` before opening a pull
  request to catch trailing whitespace or syntax issues.
- **Staging smoke test:** `./codex_ci_tasks.sh all` to replay your saved Codex
  prompts on a staging deployment.
- **Authoring a new task:** `python codex_tasks.py create --name <task>` with the
  appropriate metadata, commit the updated YAML, and share the log path with your
  team after the first run.

With these commands in place, you can reproduce the Codex automation pipeline on
any environment that can execute Python, keeping the developer and staging
experience consistent.
