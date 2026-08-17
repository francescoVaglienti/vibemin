from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vibemin.policy import ProtectedKind
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


def test_feature_base_reduces_changes_across_commits(repository: Path) -> None:
    run(repository, "git", "branch", "feature-start")
    (repository / "answer.py").write_text(
        "def answer():\n    noise = 40\n    result = 2\n    return result\n"
    )
    run(repository, "git", "add", "answer.py")
    run(repository, "git", "commit", "--quiet", "-m", "feature implementation")

    result = minimize(
        ["python verify.py"],
        root=repository,
        feature_base="feature-start",
    )

    assert result.removed_units > 0
    assert (repository / "answer.py").read_text() == (
        "def answer():\n    result = 2\n    return result\n"
    )
    assert subprocess.run(["git", "diff", "--quiet"], cwd=repository, check=False).returncode == 1


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


def test_tests_dependencies_and_visuals_are_fixed_context_by_default(
    repository: Path,
) -> None:
    (repository / "answer.py").write_text("def answer():\n    noise = 9\n    return 2\n")
    tests = repository / "tests"
    tests.mkdir()
    (tests / "test_answer.py").write_text("assert True\n")
    (repository / "package-lock.json").write_text('{"lockfileVersion": 3}\n')
    (repository / "screen.css").write_text(".button { color: blue; }\n")

    result = minimize(["python verify.py"], root=repository)

    assert (repository / "answer.py").read_text() == "def answer():\n    return 2\n"
    assert (tests / "test_answer.py").read_text() == "assert True\n"
    assert (repository / "package-lock.json").is_file()
    assert (repository / "screen.css").is_file()
    assert dict(result.protected_files) == {
        Path("package-lock.json"): ProtectedKind.DEPENDENCY,
        Path("screen.css"): ProtectedKind.VISUAL,
        Path("tests/test_answer.py"): ProtectedKind.TEST,
    }


def test_protected_changes_require_their_matching_guard(repository: Path) -> None:
    tests = repository / "tests"
    tests.mkdir()
    (tests / "test_answer.py").write_text("assert True\n")

    with pytest.raises(ValueError, match="test-strength"):
        minimize(["python verify.py"], root=repository, allow_test_changes=True)

    (repository / "screen.css").write_text(".button { color: blue; }\n")
    with pytest.raises(ValueError, match="preserve-output"):
        minimize(["python verify.py"], root=repository, allow_visual_changes=True)

    (repository / "package-lock.json").write_text('{"lockfileVersion": 3}\n')
    with pytest.raises(ValueError, match="dependency-check"):
        minimize(["python verify.py"], root=repository, allow_dependency_changes=True)


def test_test_reduction_uses_strength_oracle(repository: Path) -> None:
    tests = repository / "tests"
    tests.mkdir()
    test_file = tests / "test_answer.py"
    test_file.write_text("required = 1\nnoise = 2\n")

    minimize(
        ["python -c 'pass'"],
        root=repository,
        paths=[Path("tests")],
        allow_test_changes=True,
        test_strength_checks=[
            'python -c "from pathlib import Path; '
            "assert 'required = 1' in Path('tests/test_answer.py').read_text()\""
        ],
    )

    assert test_file.read_text() == "required = 1\n"


def test_typescript_requires_real_typecheck(repository: Path) -> None:
    typescript = repository / "feature.ts"
    typescript.write_text("export const required = 2;\nexport const noise = 9;\n")

    with pytest.raises(ValueError, match="TypeScript changes require"):
        minimize(["python -c 'pass'"], root=repository)

    typecheck = repository / "typecheck"
    typecheck.write_text("#!/bin/sh\nexit 0\n")
    typecheck.chmod(0o755)
    run(repository, "git", "add", "typecheck")
    run(repository, "git", "commit", "--quiet", "-m", "add typecheck")
    result = minimize(
        ["python -c 'pass'", "./typecheck"],
        root=repository,
        apply=False,
    )
    assert result.attempts > 0
    assert typescript.read_text().endswith("export const noise = 9;\n")


def test_security_sensitive_diff_requires_security_check(repository: Path) -> None:
    auth_file = repository / "auth.py"
    auth_file.write_text("token = 'validated'\nnoise = 9\n")

    with pytest.raises(ValueError, match="security-sensitive"):
        minimize(["python -c 'pass'"], root=repository)

    minimize(
        ["python -c 'pass'"],
        root=repository,
        security_checks=["grep -q validated auth.py"],
    )
    assert auth_file.read_text() == "token = 'validated'\n"


def test_final_check_blocks_application(repository: Path) -> None:
    proposed = "def answer():\n    noise = 40\n    return 2\n"
    (repository / "answer.py").write_text(proposed)

    with pytest.raises(VerificationError, match="final check failed"):
        minimize(
            ["python verify.py"],
            root=repository,
            final_checks=["python -c 'raise SystemExit(1)'"],
        )

    assert (repository / "answer.py").read_text() == proposed


def test_mutating_final_check_is_rejected(repository: Path) -> None:
    proposed = "def answer():\n    return 2\n"
    (repository / "answer.py").write_text(proposed)

    with pytest.raises(VerificationError, match="final checks modified"):
        minimize(
            ["python verify.py"],
            root=repository,
            final_checks=["printf '# changed\\n' >> answer.py"],
        )

    assert (repository / "answer.py").read_text() == proposed
