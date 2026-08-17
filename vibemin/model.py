"""A line-addressable representation of a working-tree diff."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Snapshot:
    """The content and executable bit of one path at one point in time."""

    content: bytes | None
    executable: bool = False


@dataclass(frozen=True)
class Unit:
    """One independently removable part of a change."""

    id: int
    path: Path
    description: str


@dataclass(frozen=True)
class _Piece:
    content: bytes
    unit_id: int | None
    emit_when_selected: bool = True


class FileChange:
    """Build variants of a file by selecting change units."""

    def __init__(
        self,
        path: Path,
        before: Snapshot,
        after: Snapshot,
        first_unit_id: int,
        reducible: bool = True,
    ) -> None:
        self.path = path
        self.before = before
        self.after = after
        self.reducible = reducible
        self.units: list[Unit] = []
        self._pieces: list[_Piece] = []
        self._binary_unit: int | None = None
        self._mode_unit: int | None = None
        self._empty_presence_unit: int | None = None
        self._next_unit_id = first_unit_id
        self._build()

    @property
    def next_unit_id(self) -> int:
        return self._next_unit_id

    def _unit(self, description: str) -> int:
        unit_id = self._next_unit_id
        self._next_unit_id += 1
        if self.reducible:
            self.units.append(Unit(unit_id, self.path, description))
        return unit_id

    def _build(self) -> None:
        before = self.before.content
        after = self.after.content
        if before == after:
            if self.before.executable != self.after.executable:
                self._mode_unit = self._unit("change executable mode")
            return

        if self._is_binary(before) or self._is_binary(after):
            self._binary_unit = self._unit("replace binary file")
            return

        before_lines = [] if before is None else before.splitlines(keepends=True)
        after_lines = [] if after is None else after.splitlines(keepends=True)

        if not before_lines and not after_lines:
            self._empty_presence_unit = self._unit("change empty-file presence")
            return

        matcher = difflib.SequenceMatcher(
            None,
            [self._comparison_line(line) for line in before_lines],
            [self._comparison_line(line) for line in after_lines],
            autojunk=False,
        )
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                self._pieces.extend(_Piece(line, None) for line in after_lines[j1:j2])
                continue
            if tag in {"delete", "replace"}:
                for line in before_lines[i1:i2]:
                    unit_id = self._unit("remove baseline line")
                    self._pieces.append(_Piece(line, unit_id, emit_when_selected=False))
            if tag in {"insert", "replace"}:
                for line in after_lines[j1:j2]:
                    unit_id = self._unit("add proposed line")
                    self._pieces.append(_Piece(line, unit_id, emit_when_selected=True))

        if self.before.executable != self.after.executable:
            self._mode_unit = self._unit("change executable mode")

    @staticmethod
    def _is_binary(content: bytes | None) -> bool:
        return content is not None and b"\0" in content[:8192]

    @staticmethod
    def _comparison_line(line: bytes) -> bytes:
        return line[:-2] + b"\n" if line.endswith(b"\r\n") else line

    def render(self, selected: set[int]) -> Snapshot:
        """Render the file for the supplied set of retained change units."""
        if not self.reducible:
            return self.after

        if self._binary_unit is not None:
            return self.after if self._binary_unit in selected else self.before
        elif self._empty_presence_unit is not None:
            content = (
                self.after.content if self._empty_presence_unit in selected else self.before.content
            )
        elif self._pieces:
            rendered = b"".join(
                piece.content
                for piece in self._pieces
                if piece.unit_id is None or (piece.unit_id in selected) == piece.emit_when_selected
            )
            if self.before.content is None and not rendered:
                content = None
            elif self.after.content is None and not rendered:
                content = None
            else:
                content = rendered
        else:
            content = self.after.content

        executable = self.before.executable
        if self._mode_unit is not None and self._mode_unit in selected:
            executable = self.after.executable
        elif self._mode_unit is None:
            executable = self.after.executable
        return Snapshot(content, executable)
