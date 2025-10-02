# Contributing

## Development setup

We use [`pre-commit`](https://pre-commit.com/) to run formatting and linting before each commit.

1. Install the tooling:
   ```bash
   pip install pre-commit
   ```
2. Install the hooks for this repository:
   ```bash
   pre-commit install
   ```
3. (Optional) Run the hooks against all files to verify the workspace:
   ```bash
   pre-commit run --all-files
   ```

The configured hooks cover Black, isort, Flake8, and basic whitespace checks to keep the codebase consistent.
