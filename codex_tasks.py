#!/usr/bin/env python3
"""Entry point for Codex task helper.

This wrapper ensures ``python codex_tasks.py`` works from the repository root
by delegating to ``scripts.codex_tasks``.
"""

from __future__ import annotations

import sys

from scripts.codex_tasks import main


if __name__ == "__main__":
    sys.exit(main(sys.argv))
