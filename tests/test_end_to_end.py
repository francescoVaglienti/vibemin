from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=root, check=True, capture_output=True, text=True)


def python_command(*args: str) -> str:
    command = [sys.executable, *args]
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def vibemin_command() -> list[str]:
    executable = os.environ.get("VIBEMIN_EXECUTABLE")
    return [str(Path(executable).resolve())] if executable else [sys.executable, "-m", "vibemin"]


def invoke_vibemin(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(root, *vibemin_command(), *args)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    run(tmp_path, "git", "init", "--quiet")
    run(tmp_path, "git", "config", "user.email", "test@example.com")
    run(tmp_path, "git", "config", "user.name", "Test")
    (tmp_path / "answer.py").write_text("def answer():\n    return 1\n")
    (tmp_path / "verify.py").write_text("from answer import answer\nassert answer() == 2\n")
    run(tmp_path, "git", "add", ".")
    run(tmp_path, "git", "commit", "--quiet", "-m", "base")
    return tmp_path


def test_cli_minimizes_a_real_repository(repository: Path) -> None:
    (repository / "answer.py").write_bytes(
        b"def answer():\r\n"
        b"    # Needless AI narration.\r\n"
        b"    unused = 40\r\n"
        b"    result = 2\r\n"
        b"    return result\r\n"
    )

    result = invoke_vibemin(repository, "--check", python_command("verify.py"))

    assert "Removed" in result.stdout
    assert (repository / "answer.py").read_bytes() == (
        b"def answer():\r\n    result = 2\r\n    return result\r\n"
    )
    run(repository, sys.executable, "verify.py")


def test_cli_keeps_tests_locks_and_visuals_as_fixed_context(repository: Path) -> None:
    (repository / "answer.py").write_text("def answer():\n    noise = 9\n    return 2\n")
    (repository / "tests").mkdir()
    (repository / "tests/test_answer.py").write_text("assert True\n")
    (repository / "package-lock.json").write_text('{"lockfileVersion": 3}\n')
    (repository / "screen.css").write_text(".button { color: blue; }\n")

    result = invoke_vibemin(repository, "--check", python_command("verify.py"))

    assert "Protected as fixed context:" in result.stdout
    assert "tests/test_answer.py (test)" in result.stdout
    assert "package-lock.json (dependency manifest or lockfile)" in result.stdout
    assert "screen.css (visual asset or stylesheet)" in result.stdout
    assert (repository / "answer.py").read_text() == "def answer():\n    return 2\n"
    assert (repository / "tests/test_answer.py").read_text() == "assert True\n"
    assert (repository / "package-lock.json").is_file()
    assert (repository / "screen.css").is_file()


@pytest.mark.selfhost
def test_vibemin_can_minimize_itself(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1]
    checkout = tmp_path / "vibemin"
    run(tmp_path, "git", "clone", "--quiet", "--local", str(source), str(checkout))
    run(checkout, "git", "config", "user.email", "test@example.com")
    run(checkout, "git", "config", "user.name", "Test")
    module = checkout / "vibemin/__init__.py"
    original = module.read_text()
    module.write_text(original + "\nSELF_TEST_NOISE = None\n")

    result = invoke_vibemin(
        checkout,
        "--check",
        python_command("-m", "pytest", "-q", "tests/test_reducer.py"),
    )

    assert "Removed" in result.stdout
    assert module.read_text() == original
