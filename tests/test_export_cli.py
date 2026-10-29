"""The headless export CLI must reject unrendered videos and never overwrite by default."""

import json
from pathlib import Path

import pytest

from haizflow.services import export_cli, video_export, video_store
import test_render_export_storage as storage_tests


@pytest.fixture
def storage():
    fixture = storage_tests.RenderExportStorageTests()
    fixture.setUpClass()
    fixture.setUp()
    try:
        yield fixture
    finally:
        fixture.tearDown()


def test_list_reports_rendered_state(storage, capsys):
    _, video = storage.make_video(content=b"render")
    assert export_cli.main(["list", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    row = next(item for item in rows if item["videoId"] == video.video_id)
    assert row["ready"] is True


def test_export_copies_verified_render(storage, capsys):
    _, video = storage.make_video(content=b"cli-export")
    out = storage.external / "out.mp4"
    assert export_cli.main(["export", video.video_id, str(out)]) == 0
    assert out.read_bytes() == b"cli-export"
    assert str(out) in capsys.readouterr().out


def test_export_refuses_overwrite_without_flag(storage, capsys):
    _, video = storage.make_video(content=b"new")
    out = storage.external / "keep.mp4"
    out.write_bytes(b"old")
    assert export_cli.main(["export", video.video_id, str(out)]) == 1
    assert out.read_bytes() == b"old"
    assert "--overwrite" in capsys.readouterr().err


def test_export_unknown_video_returns_2(storage, capsys):
    assert export_cli.main(["export", "does-not-exist", str(storage.external / "x.mp4")]) == 2
    assert "not found" in capsys.readouterr().err


def test_export_unrendered_video_returns_2(storage, capsys, monkeypatch):
    _, video = storage.make_video(content=b"x")
    monkeypatch.setattr(video_export, "current_render", lambda *a, **k: None)
    monkeypatch.setattr(export_cli, "current_render", lambda *a, **k: None)
    assert export_cli.main(["export", video.video_id, str(storage.external / "y.mp4")]) == 2
    assert "not rendered" in capsys.readouterr().err
