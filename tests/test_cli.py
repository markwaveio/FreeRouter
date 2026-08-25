from __future__ import annotations

from typing import TYPE_CHECKING

from freerouter.cli import COMMANDS, main
from freerouter.state import Event, EventKind, append_events
from tests.conftest import NOW

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_help_is_the_default_and_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    # When
    code = main([])

    # Then
    assert code == 0
    printed = capsys.readouterr().out
    for name in COMMANDS:
        assert f"freerouter {name}" in printed


def test_an_unknown_command_exits_with_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    # When
    code = main(["nope"])

    # Then
    assert code == 2
    assert "未知命令" in capsys.readouterr().err


def test_report_explains_an_empty_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    monkeypatch.setenv("FREEROUTER_STATE_DIR", str(tmp_path))

    # When
    code = main(["report"])

    # Then
    assert code == 0
    assert "模型池为空" in capsys.readouterr().out


def test_changes_renders_the_changelog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    monkeypatch.setenv("FREEROUTER_STATE_DIR", str(tmp_path))
    event = Event(
        kind=EventKind.QUARANTINED, provider="groq", model_id="dead-1", detail="missing: 已下线"
    )
    append_events(tmp_path / "changelog.jsonl", [event], NOW)

    # When
    code = main(["changes"])

    # Then
    assert code == 0
    printed = capsys.readouterr().out
    assert "quarantined" in printed
    assert "groq/dead-1" in printed
    assert "missing: 已下线" in printed


def test_changes_is_quiet_before_the_first_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    monkeypatch.setenv("FREEROUTER_STATE_DIR", str(tmp_path))

    # When
    code = main(["changes"])

    # Then
    assert code == 0
    assert "还没有变更记录" in capsys.readouterr().out
