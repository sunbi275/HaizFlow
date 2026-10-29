"""Headless export: list rendered videos and copy a finished render to a file.

Uses the same verified copy path as the desktop app. It never renders, so a
video must already be processed in HaizFlow before it can be exported here.

    python -m haizflow.services.export_cli list
    python -m haizflow.services.export_cli export VIDEO_ID DESTINATION [--overwrite]
    python -m haizflow.services.export_cli render VIDEO_ID [--export DESTINATION] [--overwrite]

`render` runs the same checkpointed pipeline the desktop app starts for a
single or batch video, without the window. It needs the video's settings and
the installed resource packs. It does not run while the app is processing
the same video.

Exit codes: 0 success, 1 error, 2 video not found or not rendered.
"""

import argparse
import json
import sys
from pathlib import Path

from haizflow.services import video_store
from haizflow.services.video_export import current_render, export_video, export_filename, project_display_name


def _list(as_json: bool) -> int:
    rows = []
    for video in video_store.list_videos():
        rows.append({
            "videoId": video.video_id,
            "name": project_display_name(video),
            "ready": bool(current_render(video, verify=False)),
            "suggestedFilename": export_filename(project_display_name(video)),
        })
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            state = "ready" if row["ready"] else "not rendered"
            print(f"{row['videoId']}\t{state}\t{row['name']}")
    return 0


def _export(video_id: str, destination: str, overwrite: bool) -> int:
    video = video_store.get_video(video_id)
    if video is None:
        print(f"error: video not found: {video_id}", file=sys.stderr)
        return 2
    if not current_render(video):
        print(f"error: video is not rendered in HaizFlow yet: {video_id}", file=sys.stderr)
        return 2
    target = Path(destination)
    if target.is_dir():
        target = target / export_filename(project_display_name(video))
    try:
        written = export_video(video, target, overwrite=overwrite)
    except FileExistsError as exc:
        print(f"error: {exc} (use --overwrite)", file=sys.stderr)
        return 1
    except Exception as exc:  # surface the verified-copy failure without a traceback
        print(f"error: export failed: {exc}", file=sys.stderr)
        return 1
    print(written)
    return 0


def _render(video_id: str, export_to: str, overwrite: bool) -> int:
    from haizflow.pipeline.process_registry import prepare_video_resume
    from haizflow.pipeline.process_video import process_video_sync

    video = video_store.get_video(video_id)
    if video is None:
        print(f"error: video not found: {video_id}", file=sys.stderr)
        return 2
    if video.project_type not in {"single", "batch"}:
        print(f"error: render supports single and batch projects only: {video_id}", file=sys.stderr)
        return 1
    try:
        if video_store.prepare_video_restart(video_id) is None:
            print(f"error: could not prepare a fresh render for {video_id}", file=sys.stderr)
            return 1
        prepare_video_resume(video_id)
        process_video_sync(video_id)
    except Exception as exc:
        print(f"error: render failed: {exc}", file=sys.stderr)
        return 1
    video = video_store.get_video(video_id)
    if not video or not current_render(video):
        print(f"error: render did not finish for {video_id}", file=sys.stderr)
        return 1
    print(f"rendered: {video_id}")
    if export_to:
        return _export(video_id, export_to, overwrite)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="haizflow-export", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list", help="List videos and whether they are rendered")
    list_parser.add_argument("--json", action="store_true", help="Print JSON")
    export_parser = sub.add_parser("export", help="Export one rendered video to a file or folder")
    export_parser.add_argument("video_id")
    export_parser.add_argument("destination", help="Output .mp4 path, or an existing folder")
    export_parser.add_argument("--overwrite", action="store_true")
    render_parser = sub.add_parser("render", help="Render a single or batch video, then optionally export it")
    render_parser.add_argument("video_id")
    render_parser.add_argument("--export", dest="export_to", default="", help="Also export to this file or folder")
    render_parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "list":
        return _list(args.json)
    if args.command == "render":
        return _render(args.video_id, args.export_to, args.overwrite)
    return _export(args.video_id, args.destination, args.overwrite)


if __name__ == "__main__":
    raise SystemExit(main())
