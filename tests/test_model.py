from pathlib import Path

from vibemin.model import FileChange, Snapshot


def test_each_changed_line_can_be_removed_independently() -> None:
    change = FileChange(
        Path("answer.py"),
        Snapshot(b"def answer():\n    return 1\n"),
        Snapshot(b"def answer():\n    noise = 99\n    return 2\n"),
        0,
    )

    all_units = {unit.id for unit in change.units}
    assert change.render(all_units).content == b"def answer():\n    noise = 99\n    return 2\n"
    assert change.render(set()).content == b"def answer():\n    return 1\n"


def test_added_file_disappears_when_all_its_lines_are_removed() -> None:
    change = FileChange(Path("extra.py"), Snapshot(None), Snapshot(b"one\ntwo\n"), 0)

    assert change.render(set()).content is None
    assert change.render({unit.id for unit in change.units}).content == b"one\ntwo\n"


def test_non_reducible_change_always_renders_target() -> None:
    change = FileChange(
        Path("context.py"), Snapshot(b"old\n"), Snapshot(b"new\n"), 0, reducible=False
    )

    assert not change.units
    assert change.render(set()).content == b"new\n"
