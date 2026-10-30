"""Local MCP server that exposes the headless export CLI to Claude.

Each tool runs `haizflow.services.export_cli` in a child process with the same
Python interpreter, so the server stays small and the CLI remains the single
code path for list, export and render. Run it from the HaizFlow venv:

    python -m haizflow.services.export_mcp

Set HAIZFLOW_HOME (and PYTHONPATH to the source's src folder) in the environment
that launches the server, as in scripts/setup-export-cli.ps1.
"""

import os
import subprocess
import sys

CLI = [sys.executable, "-m", "haizflow.services.export_cli"]


def _run(args: list[str], timeout: int | None = None) -> dict:
    # The server's own stdin/stdout carry the MCP protocol: the child must never inherit them.
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
    try:
        completed = subprocess.run(CLI + args, capture_output=True, text=True, timeout=timeout, encoding="utf-8",
                                   errors="replace", stdin=subprocess.DEVNULL, env=environment, **options)
    except subprocess.TimeoutExpired:
        return {"ok": False, "exitCode": None, "error": "timed out; the render may still be running in HaizFlow"}
    return {
        "ok": completed.returncode == 0,
        "exitCode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "error": completed.stderr.strip(),
    }


def list_videos() -> dict:
    """List HaizFlow videos and whether each one has a finished render."""
    return _run(["list", "--json"])


def export_video(video_id: str, destination: str, overwrite: bool = False) -> dict:
    """Copy a finished render to a file or folder. Fails if the video is not rendered."""
    args = ["export", video_id, destination]
    if overwrite:
        args.append("--overwrite")
    return _run(args)


def render_video(video_id: str, export_to: str = "", overwrite: bool = False) -> dict:
    """Run the HaizFlow pipeline for a single or batch video, optionally exporting it.

    This can take a long time and needs the installed resource packs.
    """
    args = ["render", video_id]
    if export_to:
        args += ["--export", export_to]
    if overwrite:
        args.append("--overwrite")
    return _run(args)


def build_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("haizflow-export")
    server.tool()(list_videos)
    server.tool()(export_video)
    server.tool()(render_video)
    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
