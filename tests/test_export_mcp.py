"""The MCP wrapper must map tool calls onto the export CLI without changing its behavior."""

import subprocess
from types import SimpleNamespace

from haizflow.services import export_mcp


def _capture(monkeypatch, returncode=0, stdout="", stderr=""):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(export_mcp.subprocess, "run", fake_run)
    return calls


def test_list_calls_cli_with_json(monkeypatch):
    calls = _capture(monkeypatch, stdout='[{"videoId": "a"}]')
    result = export_mcp.list_videos()
    args, _ = calls[0]
    assert args[-2:] == ["list", "--json"]
    assert result["ok"] is True and result["stdout"] == '[{"videoId": "a"}]'


def test_export_passes_overwrite_flag(monkeypatch):
    calls = _capture(monkeypatch)
    export_mcp.export_video("vid", "D:/out.mp4", overwrite=True)
    args, _ = calls[0]
    assert args[-4:] == ["export", "vid", "D:/out.mp4", "--overwrite"]


def test_render_with_export_destination(monkeypatch):
    calls = _capture(monkeypatch)
    export_mcp.render_video("vid", export_to="D:/out.mp4")
    args, _ = calls[0]
    assert args[-4:] == ["render", "vid", "--export", "D:/out.mp4"]


def test_failure_returns_stderr_and_not_ok(monkeypatch):
    _capture(monkeypatch, returncode=2, stderr="error: video not found: x")
    result = export_mcp.export_video("x", "D:/y.mp4")
    assert result["ok"] is False and result["exitCode"] == 2
    assert "not found" in result["error"]


def test_render_timeout_is_reported(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(export_mcp.subprocess, "run", boom)
    result = export_mcp.render_video("vid")
    assert result["ok"] is False and "timed out" in result["error"]


def test_server_registers_three_tools():
    server = export_mcp.build_server()
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert names == {"list_videos", "export_video", "render_video"}


def test_child_never_inherits_stdin_and_runs_in_utf8(monkeypatch):
    calls = _capture(monkeypatch)
    export_mcp.list_videos()
    _, kwargs = calls[0]
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["env"]["PYTHONUTF8"] == "1"
    assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
