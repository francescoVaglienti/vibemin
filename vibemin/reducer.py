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
    write_snapshot,
)
from vibemin.model import FileChange


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
                command,
                cwd=root,
                env=environment,
                shell=True,
                executable="/bin/sh",
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
                command,
                cwd=root,
                env=environment,
                shell=True,
                executable="/bin/sh",
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
    paths: Iterable[Path] = (),
    preserve_outputs: Iterable[str] = (),
    timeout: float = 300,
    max_attempts: int = 500,
    apply: bool = True,
    progress: ProgressCallback | None = None,
) -> MinimizeResult:
    """Minimize current changes while every verification command remains green."""
    commands_tuple = tuple(commands)
    preserve_commands = tuple(preserve_outputs)
    if not commands_tuple:
        raise ValueError("at least one verification command is required")
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be greater than zero")
    invocation_root = (root or Path.cwd()).resolve()
    repo_root = find_root(invocation_root)
    assert_no_staged_changes(repo_root)
    base_commit = resolve_base(repo_root, base)
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
    changes, all_units = load_changes(repo_root, base_commit, selected_paths)
    if not changes:
        raise GitError("there are no tracked or untracked changes to minimize")
    if not all_units:
        raise GitError("the selected paths contain no minimizable changes")

    with Worktree(repo_root, base_commit) as sandbox:
        _materialize(sandbox, changes, all_units)
        selected, attempts = _reduce(
            sandbox,
            changes,
            all_units,
            commands_tuple,
            preserve_commands,
            timeout,
            max_attempts,
            progress,
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
    )
