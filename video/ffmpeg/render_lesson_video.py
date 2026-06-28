#!/usr/bin/env python3
"""Render lesson audio and flowing ASS subtitles over an image or looping video."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).with_name("video_style.json")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ffmpeg_filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def format_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render lesson audio and flowing ASS subtitles over a static image or looping video."
    )
    parser.add_argument("audio", type=Path, help="Lesson audio file.")
    parser.add_argument("subtitles", type=Path, help="Flowing .ass subtitle file.")
    backgrounds = parser.add_mutually_exclusive_group(required=True)
    backgrounds.add_argument("--background-image", type=Path)
    backgrounds.add_argument("--background-video", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--preview-start", type=float, default=None, help="Preview start time in seconds.")
    parser.add_argument("--preview-duration", type=float, default=None, help="Preview duration in seconds.")
    parser.add_argument("--video-codec", default="libx264")
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--audio-codec", default="aac")
    parser.add_argument("--audio-bitrate", default="192k")
    parser.add_argument("--dry-run", action="store_true", help="Print the FFmpeg command without rendering.")
    args = parser.parse_args()

    for label, path in (
        ("Audio", args.audio),
        ("Subtitles", args.subtitles),
        ("Config", args.config),
        ("Background", args.background_image or args.background_video),
    ):
        if not path or not path.exists():
            parser.error(f"{label} file not found: {path}")
    if args.subtitles.suffix.lower() != ".ass":
        parser.error("The renderer requires an ASS subtitle file for flowing styled text.")
    if args.preview_start is not None and args.preview_start < 0:
        parser.error("--preview-start must be zero or greater.")
    if args.preview_duration is not None and args.preview_duration <= 0:
        parser.error("--preview-duration must be greater than zero.")

    try:
        config = load_json(args.config)
        video: dict[str, Any] = config["video"]
        width = int(video["width"])
        height = int(video["height"])
        fps = int(video["fps"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        parser.error(f"Invalid video config: {exc}")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        parser.error("FFmpeg was not found on PATH.")

    output = args.output or args.audio.with_suffix(".mp4")
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [ffmpeg, "-y"]
    if args.background_image:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(args.background_image)]
    else:
        command += ["-stream_loop", "-1", "-i", str(args.background_video)]
    if args.preview_start is not None:
        command += ["-ss", str(args.preview_start)]
    command += ["-i", str(args.audio)]

    subtitle_path = ffmpeg_filter_path(args.subtitles)
    timeline_offset = args.preview_start or 0.0
    video_filter = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},setpts=PTS+{timeline_offset}/TB,"
        f"subtitles=filename='{subtitle_path}',setpts=PTS-STARTPTS[video]"
    )
    command += ["-filter_complex", video_filter, "-map", "[video]", "-map", "1:a:0"]

    if args.preview_duration is not None:
        command += ["-t", str(args.preview_duration)]

    command += [
        "-c:v",
        args.video_codec,
        "-preset",
        args.preset,
        "-crf",
        str(args.crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        args.audio_codec,
        "-b:a",
        args.audio_bitrate,
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]

    print(f"Output: {output}")
    print(f"Resolution: {width}x{height} at {fps} fps")
    print(f"FFmpeg command: {format_command(command)}")
    if args.dry_run:
        return

    subprocess.run(command, check=True)
    print(f"Done: {output}")


if __name__ == "__main__":
    main()
