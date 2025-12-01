from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import subprocess
from pathlib import Path

import pytest


def load_codex_module():
    repo_root = Path(__file__).resolve().parent.parent
    loader = importlib.machinery.SourceFileLoader("codex_cli", str(repo_root / "codex"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader  # for type checkers
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


codex = load_codex_module()

apply_trailing_whitespace_fix = codex.apply_trailing_whitespace_fix
compile_python_files = codex.compile_python_files
iter_python_files = codex.iter_python_files
parse_args = codex.parse_args
run_review = codex.run_review


def test_parse_args_defaults_uses_cwd():
    args = parse_args(["review"])

    assert args.repo == Path.cwd()
    assert args.apply_fixes is False
    assert args.no_compile is False


def test_iter_python_files_excludes_common_directories(tmp_path: Path):
    keep_file = tmp_path / "keep.py"
    keep_file.write_text("print('ok')\n", encoding="utf-8")

    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "skip.py").write_text("print('skip')\n", encoding="utf-8")

    found = list(iter_python_files(tmp_path))

    assert keep_file in found
    assert all(path.name != "skip.py" for path in found)


def test_apply_trailing_whitespace_fix_strips_and_adds_newline(tmp_path: Path):
    target = tmp_path / "whitespace.py"
    target.write_text("print('ok')   \nsecond   \n\n", encoding="utf-8")

    changed = apply_trailing_whitespace_fix([target])

    assert changed == [target]
    assert target.read_text(encoding="utf-8") == "print('ok')\nsecond\n\n"


def test_compile_python_files_returns_failures(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("print('ok')\n", encoding="utf-8")

    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")

    success, output = compile_python_files([good, bad])

    assert success is False
    assert "bad.py" in output


def test_run_review_reports_counts(tmp_path: Path):
    sample = tmp_path / "sample.py"
    sample.write_text("print('ok')\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    result = run_review(tmp_path, apply_fixes=False, skip_compile=True)

    assert result.repo == tmp_path.resolve()
    assert result.python_file_count == 1
    assert result.total_python_lines == 1
    assert "sample.py" in result.git_status
