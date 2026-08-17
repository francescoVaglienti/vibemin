"""Conservative defaults for changes whose correctness is not proved by ordinary tests."""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path


class ProtectedKind(str, Enum):
    TEST = "test"
    DEPENDENCY = "dependency manifest or lockfile"
    VISUAL = "visual asset or stylesheet"


_TEST_DIRECTORIES = {"test", "tests", "__tests__", "spec", "specs", "__snapshots__"}
_DEPENDENCY_FILES = {
    "bun.lock",
    "bun.lockb",
    "cargo.lock",
    "cargo.toml",
    "composer.json",
    "composer.lock",
    "gemfile",
    "gemfile.lock",
    "go.mod",
    "go.sum",
    "package-lock.json",
    "package.json",
    "pipfile",
    "pipfile.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pyproject.toml",
    "uv.lock",
    "yarn.lock",
}
_VISUAL_SUFFIXES = {
    ".avif",
    ".bmp",
    ".css",
    ".eot",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".less",
    ".otf",
    ".png",
    ".sass",
    ".scss",
    ".svg",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
}
_SECURITY_MARKERS = (
    b"authorization",
    b"cookie",
    b"cors",
    b"csrf",
    b"jwt",
    b"oauth",
    b"oidc",
    b"password",
    b"permission",
    b"secret",
    b"session",
    b"tenant",
    b"token",
)
_SECURITY_PATH_MARKERS = {
    "auth",
    "authentication",
    "authorization",
    "middleware",
    "permission",
    "security",
    "tenant",
}
_TYPESCRIPT_SUFFIXES = {".ts", ".tsx", ".mts", ".cts"}
_DIRECT_TYPECHECK = re.compile(
    r"(?:^|&&|\|\||;)\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=[^ ]+\s+)*"
    r"(?:(?:npx|bunx|pnpm\s+exec|yarn\s+dlx)\s+)?"
    r"(?:[\w./-]*(?:typecheck|type-check)|(?:[\w./-]*/)?tsc)(?:\s|$)"
)


def protected_kind(path: Path) -> ProtectedKind | None:
    """Return why a changed path is fixed context under the safe defaults."""

    lowered_parts = tuple(part.casefold() for part in path.parts)
    name = path.name.casefold()
    if any(part in _TEST_DIRECTORIES for part in lowered_parts):
        return ProtectedKind.TEST
    if name.startswith("test_") or name.endswith("_test.py"):
        return ProtectedKind.TEST
    if re.search(r"\.(?:test|spec)\.[^.]+$", name):
        return ProtectedKind.TEST
    if name in _DEPENDENCY_FILES or name.startswith("requirements") and name.endswith(".txt"):
        return ProtectedKind.DEPENDENCY
    if path.suffix.casefold() in _VISUAL_SUFFIXES:
        return ProtectedKind.VISUAL
    return None


def is_security_sensitive(path: Path, content: bytes | None) -> bool:
    """Recognise diffs that need a security-specific oracle in addition to normal tests."""

    stems = {part.casefold().split(".", 1)[0] for part in path.parts}
    if stems & _SECURITY_PATH_MARKERS:
        return True
    lowered = (content or b"").lower()
    return any(marker in lowered for marker in _SECURITY_MARKERS)


def has_typescript(paths: list[Path]) -> bool:
    return any(path.suffix.casefold() in _TYPESCRIPT_SUFFIXES for path in paths)


def has_typecheck(commands: tuple[str, ...], root: Path) -> bool:
    """Accept direct typecheck commands or package scripts that actually invoke one."""

    lowered_commands = tuple(command.casefold() for command in commands)
    if any(_DIRECT_TYPECHECK.search(command) for command in lowered_commands):
        return True

    scripts: dict[str, str] = {}
    for manifest in root.rglob("package.json"):
        if ".git" in manifest.parts or "node_modules" in manifest.parts:
            continue
        try:
            raw_scripts = json.loads(manifest.read_text()).get("scripts", {})
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            continue
        if isinstance(raw_scripts, dict):
            scripts.update(
                (str(name).casefold(), str(command).casefold())
                for name, command in raw_scripts.items()
            )

    for name, script in scripts.items():
        if "tsc" not in script and "typecheck" not in script and "type-check" not in script:
            continue
        invocation = re.compile(rf"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?{re.escape(name)}\b")
        if any(invocation.search(command) for command in lowered_commands):
            return True
    return False
