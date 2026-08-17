from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vibemin.reducer import VerificationError, minimize


def run(root: Path, *args: str) -> None:
    subprocess.run(args, cwd=root, check=True, capture_output=True)


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


def test_minimize_removes_unnecessary_ai_lines(repository: Path) -> None:
    (repository / "answer.py").write_text(
        "def answer():\n"
        "    # This is needless AI narration.\n"
        "    unused = 40\n"
        "    result = 2\n"
        "    return result\n"
    )

    result = minimize(["python verify.py"], root=repository)

    assert result.removed_units > 0
    assert (repository / "answer.py").read_text() == (
        "def answer():\n    result = 2\n    return result\n"
    )
    run(repository, "python", "verify.py")


def test_dry_run_does_not_touch_checkout(repository: Path) -> None:
    proposed = "def answer():\n    noise = 40\n    return 2\n"
    (repository / "answer.py").write_text(proposed)

    result = minimize(["python verify.py"], root=repository, apply=False)

    assert result.removed_units > 0
    assert (repository / "answer.py").read_text() == proposed


def test_failing_original_is_rejected_without_touching_checkout(repository: Path) -> None:
    proposed = "def answer():\n    unused = 40\n    return 3\n"
    (repository / "answer.py").write_text(proposed)

    with pytest.raises(VerificationError):
        minimize(["python verify.py"], root=repository)

    assert (repository / "answer.py").read_text() == proposed


def test_paths_are_relative_to_invocation_directory(repository: Path) -> None:
    package = repository / "package"
    package.mkdir()
    answer = package / "extra.py"
    answer.write_text("needed = 2\nnoise = 9\n")
    (repository / "verify.py").write_text("from package.extra import needed\nassert needed == 2\n")

    minimize(["python verify.py"], root=package, paths=[Path("extra.py")])

    assert answer.read_text() == "needed = 2\n"


def test_mutating_check_is_rejected(repository: Path) -> None:
    proposed = "def answer():\n    return 2\n"
    (repository / "answer.py").write_text(proposed)

    with pytest.raises(VerificationError, match="non-mutating"):
        minimize(["printf '# changed\\n' >> answer.py"], root=repository)

    assert (repository / "answer.py").read_text() == proposed


def test_preserved_output_prevents_contract_removal(repository: Path) -> None:
    contract = repository / "contract.txt"
    contract.write_text("test_one\ntest_two\n")

    result = minimize(
        ["python -c 'pass'"],
        root=repository,
        preserve_outputs=["python -c \"print(open('contract.txt').read(), end='')\""],
    )

    assert contract.read_text() == "test_one\ntest_two\n"
    assert result.retained_units >= 2
