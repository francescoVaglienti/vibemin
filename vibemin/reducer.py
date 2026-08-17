"""Test-guided delta reduction of a Git diff."""

from __future__ import annotations

import math
import os
import subprocess
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

from vibemin.git import (
    GitError,
    Worktree,
    assert_no_staged_changes,
    current_snapshot,
    find_root,
    load_changes,
    resolve_base,
    resolve_feature_base,
    write_snapshot,
)
from vibemin.model import FileChange
from vibemin.policy import (
    ProtectedKind,
    has_typecheck,
    has_typescript,
    is_security_sensitive,
    protected_kind,
)


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Attempt:
    number: int
    retained_units: int
    passed: bool
    seconds: float
    failed_command: str | None = None
    output: str = ""


@dataclass(frozen=True)
class MinimizeResult:
    root: Path
    original_units: int
    retained_units: int
    attempts: int
    applied: bool
    changed_files: tuple[Path, ...]
    protected_files: tuple[tuple[Path, ProtectedKind], ...] = ()

    @property
    def removed_units(self) -> int:
        return self.original_units - self.retained_units


ProgressCallback = Callable[[Attempt], None]


def _materialize(root: Path, changes: Iterable[FileChange], selected: set[int]) -> None:
    for change in changes:
        write_snapshot(root, change.path, change.render(selected))


def _run_checks(
    root: Path, commands: tuple[str, ...], timeout: float
) -> tuple[bool, str | None, str]:
    environment = os.environ.copy()
    environment["VIBEMIN_ROOT"] = str(root)
    for command in commands:
        try:
            process = subprocess.run(
                ["/bin/sh", "-c", command],
                cwd=root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            return False, command, f"timed out after {timeout:g}s\n{output}"
        if process.returncode:
            return False, command, process.stdout[-4000:]
    return True, None, ""


def _capture_preserved_outputs(
    root: Path, commands: tuple[str, ...], timeout: float
) -> tuple[bool, str | None, str, tuple[str, ...]]:
    outputs: list[str] = []
    environment = os.environ.copy()
    environment["VIBEMIN_ROOT"] = str(root)
    for command in commands:
        try:
            process = subprocess.run(
                ["/bin/sh", "-c", command],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            return False, command, f"timed out after {timeout:g}s\n{output}", ()
        combined = process.stdout + process.stderr
        if process.returncode:
            return False, command, combined[-4000:], ()
        outputs.append(combined)
    return True, None, "", tuple(outputs)


def _preserved_output_diff(command: str, expected: str, actual: str) -> str:
    difference = "".join(
        unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="original output",
            tofile="candidate output",
            n=2,
        )
    )
    return f"preserved output changed for: {command}\n{difference[-4000:]}"


def _chunks(items: list[int], count: int) -> Iterable[list[int]]:
    size = math.ceil(len(items) / count)
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _reduce(
    sandbox: Path,
    changes: list[FileChange],
    initial: set[int],
    commands: tuple[str, ...],
    preserve_commands: tuple[str, ...],
    timeout: float,
    max_attempts: int,
    progress: ProgressCallback | None,
) -> tuple[set[int], int]:
    selected = set(initial)
    cache: dict[frozenset[int], bool] = {}
    attempts = 0
    preserved_outputs: tuple[str, ...] | None = None

    def verify(candidate: set[int]) -> bool:
        nonlocal attempts, preserved_outputs
        key = frozenset(candidate)
        if key in cache:
            return cache[key]
        if attempts >= max_attempts:
            return False
        _materialize(sandbox, changes, candidate)
        expected_snapshots = {change.path: change.render(candidate) for change in changes}
        started = time.monotonic()
        passed, failed_command, output = _run_checks(sandbox, commands, timeout)
        if passed and preserve_commands:
            passed, failed_command, output, observed = _capture_preserved_outputs(
                sandbox, preserve_commands, timeout
            )
            if passed and preserved_outputs is None:
                preserved_outputs = observed
            elif passed:
                for command, expected_output, actual_output in zip(
                    preserve_commands, preserved_outputs, observed, strict=True
                ):
                    if actual_output != expected_output:
                        passed = False
                        failed_command = command
                        output = _preserved_output_diff(command, expected_output, actual_output)
                        break
        mutated = [
            str(change.path)
            for change in changes
            if current_snapshot(sandbox, change.path) != expected_snapshots[change.path]
        ]
        if mutated:
            raise VerificationError(
                "verification commands modified candidate files (checks must be non-mutating): "
                + ", ".join(mutated)
            )
        attempts += 1
        cache[key] = passed
        if progress:
            progress(
                Attempt(
                    attempts,
                    len(candidate),
                    passed,
                    time.monotonic() - started,
                    failed_command,
                    output,
                )
            )
        return passed

    if not verify(selected):
        raise VerificationError("the original changes do not pass all verification commands")

    granularity = 2
    while selected and attempts < max_attempts:
        ordered = sorted(selected)
        reduced = False
        for chunk in _chunks(ordered, granularity):
            candidate = selected.difference(chunk)
            if verify(candidate):
                selected = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
            if attempts >= max_attempts:
                break
        if reduced:
            continue
        if granularity >= len(selected):
            break
        granularity = min(len(selected), granularity * 2)

    _materialize(sandbox, changes, selected)
    return selected, attempts


def _assert_original_unchanged(root: Path, changes: Iterable[FileChange]) -> None:
    altered = [
        str(change.path)
        for change in changes
        if current_snapshot(root, change.path) != change.after
    ]
    if altered:
        raise GitError("working tree changed during minimization: " + ", ".join(altered))


def minimize(
    commands: Iterable[str],
    *,
    root: Path | None = None,
    base: str = "HEAD",
    feature_base: str | None = None,
    paths: Iterable[Path] = (),
    preserve_outputs: Iterable[str] = (),
    final_checks: Iterable[str] = (),
    security_checks: Iterable[str] = (),
    test_strength_checks: Iterable[str] = (),
    dependency_checks: Iterable[str] = (),
    allow_test_changes: bool = False,
    allow_dependency_changes: bool = False,
    allow_visual_changes: bool = False,
    allow_untyped_typescript: bool = False,
    timeout: float = 300,
    max_attempts: int = 500,
    apply: bool = True,
    progress: ProgressCallback | None = None,
) -> MinimizeResult:
    """Minimize current changes while every verification command remains green."""
    commands_tuple = tuple(commands)
    preserve_commands = tuple(preserve_outputs)
    final_commands = tuple(final_checks)
    security_commands = tuple(security_checks)
    test_strength_commands = tuple(test_strength_checks)
    dependency_commands = tuple(dependency_checks)
    if not commands_tuple:
        raise ValueError("at least one verification command is required")
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be greater than zero")
    invocation_root = (root or Path.cwd()).resolve()
    repo_root = find_root(invocation_root)
    assert_no_staged_changes(repo_root)
    base_commit = (
        resolve_feature_base(repo_root, feature_base)
        if feature_base is not None
        else resolve_base(repo_root, base)
    )
    selected_paths_list: list[Path] = []
    for supplied_path in paths:
        absolute = Path(supplied_path)
        if not absolute.is_absolute():
            absolute = invocation_root / absolute
        try:
            selected_paths_list.append(absolute.resolve().relative_to(repo_root))
        except ValueError as error:
            raise GitError(f"selected path is outside the repository: {supplied_path}") from error
    selected_paths = tuple(selected_paths_list)
    kinds_to_protect = {
        kind
        for kind, allowed in (
            (ProtectedKind.TEST, allow_test_changes),
            (ProtectedKind.DEPENDENCY, allow_dependency_changes),
            (ProtectedKind.VISUAL, allow_visual_changes),
        )
        if not allowed
    }
    if allow_test_changes and not (test_strength_commands or preserve_commands):
        raise ValueError("minimizing tests requires --test-strength-check or --preserve-output")
    if allow_dependency_changes and not dependency_commands:
        raise ValueError("minimizing dependency files requires --dependency-check")
    if allow_visual_changes and not preserve_commands:
        raise ValueError("minimizing visual files requires deterministic --preserve-output output")

    changes, all_units = load_changes(
        repo_root,
        base_commit,
        selected_paths,
        protected=lambda path: protected_kind(path) in kinds_to_protect,
    )
    if not changes:
        raise GitError("there are no tracked or untracked changes to minimize")
    protected_files = tuple(
        (change.path, kind)
        for change in changes
        if (kind := protected_kind(change.path)) in kinds_to_protect
    )
    if not all_units:
        if protected_files:
            paths_text = ", ".join(str(path) for path, _kind in protected_files)
            raise GitError(
                "the selected paths contain only protected changes: "
                f"{paths_text}; use the matching --allow-*-changes option with its guard"
            )
        raise GitError("the selected paths contain no minimizable changes")

    reducible_paths = [change.path for change in changes if change.units]
    all_candidate_commands = (
        commands_tuple + security_commands + test_strength_commands + dependency_commands
    )
    if has_typescript(reducible_paths) and not allow_untyped_typescript:
        if not has_typecheck(all_candidate_commands, repo_root):
            raise ValueError(
                "TypeScript changes require a tsc/typecheck command; "
                "use --allow-untyped-typescript only when this is intentional"
            )
    sensitive = [
        change.path
        for change in changes
        if change.units and is_security_sensitive(change.path, change.after.content)
    ]
    if sensitive and not security_commands:
        raise ValueError(
            "security-sensitive changes require --security-check: "
            + ", ".join(str(path) for path in sensitive)
        )

    with Worktree(repo_root, base_commit) as sandbox:
        _materialize(sandbox, changes, all_units)
        selected, attempts = _reduce(
            sandbox,
            changes,
            all_units,
            all_candidate_commands,
            preserve_commands,
            timeout,
            max_attempts,
            progress,
        )
        if final_commands:
            expected_snapshots = {change.path: change.render(selected) for change in changes}
            passed, failed_command, output = _run_checks(sandbox, final_commands, timeout)
            if not passed:
                raise VerificationError(f"final check failed: {failed_command}\n{output}".rstrip())
            mutated = [
                str(change.path)
                for change in changes
                if current_snapshot(sandbox, change.path) != expected_snapshots[change.path]
            ]
            if mutated:
                raise VerificationError(
                    "final checks modified candidate files (checks must be non-mutating): "
                    + ", ".join(mutated)
                )
        final = {change.path: change.render(selected) for change in changes}

    changed_files = tuple(change.path for change in changes if final[change.path] != change.after)
    if apply:
        _assert_original_unchanged(repo_root, changes)
        for change in changes:
            if final[change.path] != change.after:
                write_snapshot(repo_root, change.path, final[change.path])

    return MinimizeResult(
        root=repo_root,
        original_units=len(all_units),
        retained_units=len(selected),
        attempts=attempts,
        applied=apply,
        changed_files=changed_files,
        protected_files=protected_files,
    )
