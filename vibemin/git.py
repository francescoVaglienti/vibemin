"""Small, deliberately narrow Git adapter."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from contextlib import AbstractContextManager
from pathlib import Path

from vibemin.model import FileChange, Snapshot


class GitError(RuntimeError):
    pass


def _run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    process = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if check and process.returncode:
        message = process.stderr.decode(errors="replace").strip()
        raise GitError(message or f"git {' '.join(args)} failed")
    return process


def find_root(start: Path) -> Path:
    output = _run(start, "rev-parse", "--show-toplevel").stdout
    return Path(os.fsdecode(output).strip()).resolve()


def assert_no_staged_changes(root: Path) -> None:
    result = _run(root, "diff", "--cached", "--quiet", check=False)
    if result.returncode == 1:
        raise GitError(
            "staged changes are not supported; commit or unstage them before running vibemin"
        )
    if result.returncode:
        raise GitError(result.stderr.decode(errors="replace").strip())


def resolve_base(root: Path, base: str) -> str:
    return _run(root, "rev-parse", "--verify", f"{base}^{{commit}}").stdout.decode().strip()


def _nul_paths(output: bytes) -> list[Path]:
    return [Path(os.fsdecode(value)) for value in output.split(b"\0") if value]


def changed_paths(root: Path, base: str) -> list[Path]:
    tracked = _nul_paths(
        _run(root, "diff", "--name-only", "-z", "--diff-filter=ACDMRTUXB", base, "--").stdout
    )
    untracked = _nul_paths(_run(root, "ls-files", "--others", "--exclude-standard", "-z").stdout)
    return sorted(set(tracked + untracked), key=lambda path: os.fsencode(path))


def _base_snapshot(root: Path, base: str, path: Path) -> Snapshot:
    spec = f"{base}:{path.as_posix()}"
    exists = _run(root, "cat-file", "-e", spec, check=False).returncode == 0
    if not exists:
        return Snapshot(None)
    tree_line = _run(root, "ls-tree", base, "--", path.as_posix()).stdout.split(None, 1)
    mode = tree_line[0] if tree_line else b""
    if mode not in {b"100644", b"100755"}:
        raise GitError(f"unsupported baseline path (only regular files are supported): {path}")
    content = _run(root, "show", spec).stdout
    executable = mode == b"100755"
    return Snapshot(content, executable)


def current_snapshot(root: Path, path: Path) -> Snapshot:
    absolute = root / path
    if not absolute.exists() and not absolute.is_symlink():
        return Snapshot(None)
    if absolute.is_symlink() or not absolute.is_file():
        raise GitError(f"unsupported changed path (only regular files are supported): {path}")
    mode = absolute.stat().st_mode
    return Snapshot(absolute.read_bytes(), bool(mode & stat.S_IXUSR))


def load_changes(
    root: Path, base: str, selected_paths: tuple[Path, ...]
) -> tuple[list[FileChange], set[int]]:
    changes: list[FileChange] = []
    selected_units: set[int] = set()
    next_unit_id = 0
    for path in changed_paths(root, base):
        reducible = not selected_paths or any(
            path == selected or selected in path.parents for selected in selected_paths
        )
        change = FileChange(
            path,
            _base_snapshot(root, base, path),
            current_snapshot(root, path),
            next_unit_id,
            reducible,
        )
        next_unit_id = change.next_unit_id
        changes.append(change)
        selected_units.update(unit.id for unit in change.units)
    return changes, selected_units


def write_snapshot(root: Path, path: Path, snapshot: Snapshot) -> None:
    absolute = root / path
    if snapshot.content is None:
        if absolute.exists():
            absolute.unlink()
        return
    absolute.parent.mkdir(parents=True, exist_ok=True)
    temporary = absolute.with_name(f".{absolute.name}.vibemin.tmp")
    temporary.write_bytes(snapshot.content)
    temporary.chmod(0o755 if snapshot.executable else 0o644)
    temporary.replace(absolute)


class Worktree(AbstractContextManager[Path]):
    """A disposable detached worktree at the baseline revision."""

    def __init__(self, root: Path, base: str) -> None:
        self.root = root
        self.base = base
        self.path: Path | None = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="vibemin-"))
        try:
            _run(self.root, "worktree", "add", "--detach", "--quiet", str(self.path), self.base)
        except Exception:
            shutil.rmtree(self.path, ignore_errors=True)
            self.path = None
            raise
        return self.path

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self.path is None:
            return
        _run(self.root, "worktree", "remove", "--force", str(self.path), check=False)
        shutil.rmtree(self.path, ignore_errors=True)
        _run(self.root, "worktree", "prune", check=False)
