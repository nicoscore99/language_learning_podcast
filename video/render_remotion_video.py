#!/usr/bin/env python3
"""Render a Remotion composition and write a video manifest sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ENTRY = Path("video/remotion/index.ts")
DEFAULT_COMPOSITION = "PodcastFinal"
PUBLIC_RENDER_ASSETS = Path("public/render-assets")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_text(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def git_metadata() -> dict[str, Any] | None:
    commit = run_text(["git", "rev-parse", "HEAD"])
    if not commit:
        return None
    status = run_text(["git", "status", "--short"]) or ""
    return {
        "commit": commit,
        "dirty": bool(status.strip()),
        "status_short": status.splitlines(),
    }


def ffprobe_metadata(path: Path) -> dict[str, Any] | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return None

    output = run_text([
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(path),
    ])
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def default_manifest_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.video.manifest.json")


def format_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def is_local_path(src: str) -> bool:
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", src)
        or src.startswith("\\\\")
        or src.startswith("file:///")
    )


def local_media_path(src: str) -> Path:
    if src.startswith("file:///"):
        return Path(src.removeprefix("file:///").replace("/", "\\"))
    return Path(src)


def stage_public_asset(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    digest = sha256_file(path)[:16]
    suffix = path.suffix or ".bin"
    PUBLIC_RENDER_ASSETS.mkdir(parents=True, exist_ok=True)
    target = PUBLIC_RENDER_ASSETS / f"{path.stem}-{digest}{suffix}"

    if not target.exists() or target.stat().st_size != path.stat().st_size:
        shutil.copy2(path, target)

    return target.relative_to("public").as_posix()


def prepare_render_props(
    props: dict[str, Any],
    original_props_path: Path,
    output: Path,
) -> tuple[Path, dict[str, str] | None]:
    audio_src = props.get("audioSrc")
    if not isinstance(audio_src, str) or not is_local_path(audio_src):
        return original_props_path, None

    source = local_media_path(audio_src)
    staged_src = stage_public_asset(source)
    render_props = dict(props)
    render_props["audioSrc"] = staged_src

    render_props_path = output.with_name(f"{output.stem}.render.props.json")
    render_props_path.parent.mkdir(parents=True, exist_ok=True)
    render_props_path.write_text(
        json.dumps(render_props, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return render_props_path, {
        "original_audio_src": audio_src,
        "staged_audio_src": staged_src,
        "render_props": str(render_props_path),
    }


def resolve_executable(name: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved

    if sys.platform == "win32" and not Path(name).suffix:
        for suffix in (".cmd", ".exe", ".bat"):
            resolved = shutil.which(f"{name}{suffix}")
            if resolved:
                return resolved

    raise FileNotFoundError(
        f"Could not find renderer executable '{name}' on PATH. "
        "Install Node.js/npm or pass --renderer with the full path, e.g. "
        r"--renderer C:\Program Files\nodejs\npx.cmd"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a Remotion composition and write a video manifest sidecar."
    )
    parser.add_argument("--entry", type=Path, default=DEFAULT_ENTRY)
    parser.add_argument("--composition", default=DEFAULT_COMPOSITION)
    parser.add_argument("--props", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video-manifest", type=Path, default=None)
    parser.add_argument("--audio-manifest", type=Path, default=None)
    parser.add_argument("--renderer", default="npx", help="Command used to invoke Remotion.")
    parser.add_argument("--codec", default=None, help="Optional Remotion codec, e.g. h264.")
    parser.add_argument("--crf", type=int, default=None, help="Optional Remotion CRF.")
    parser.add_argument("--concurrency", default=None, help="Optional Remotion concurrency.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for label, path in (
        ("Entry", args.entry),
        ("Props", args.props),
        ("Audio manifest", args.audio_manifest),
    ):
        if path is not None and not path.exists():
            parser.error(f"{label} file not found: {path}")

    props = load_json(args.props)
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    video_manifest = args.video_manifest or default_manifest_path(output)
    try:
        render_props_path, staged_asset = prepare_render_props(props, args.props, output)
    except FileNotFoundError as error:
        parser.error(str(error))

    try:
        renderer_executable = resolve_executable(args.renderer)
    except FileNotFoundError as error:
        parser.error(str(error))

    command = [
        renderer_executable,
        "remotion",
        "render",
        str(args.entry),
        args.composition,
        str(output),
        f"--props={render_props_path}",
    ]
    if args.codec:
        command.append(f"--codec={args.codec}")
    if args.crf is not None:
        command.append(f"--crf={args.crf}")
    if args.concurrency:
        command.append(f"--concurrency={args.concurrency}")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tool": {
            "script": str(Path(__file__).as_posix()),
            "python": sys.version,
            "renderer": args.renderer,
            "renderer_executable": renderer_executable,
        },
        "git": git_metadata(),
        "remotion": {
            "entry": str(args.entry),
            "composition": args.composition,
            "command": command,
            "command_string": format_command(command),
            "codec": args.codec,
            "crf": args.crf,
            "concurrency": args.concurrency,
            "staged_asset": staged_asset,
        },
        "inputs": {
            "props": {
                "path": str(args.props),
                "sha256": sha256_file(args.props),
            },
            "render_props": (
                {
                    "path": str(render_props_path),
                    "sha256": sha256_file(render_props_path),
                }
                if render_props_path != args.props
                else None
            ),
            "audio_manifest": (
                {
                    "path": str(args.audio_manifest),
                    "sha256": sha256_file(args.audio_manifest),
                }
                if args.audio_manifest
                else None
            ),
        },
        "props_snapshot": props,
        "output": {
            "path": str(output),
        },
    }

    if args.dry_run:
        print(format_command(command))
        video_manifest.parent.mkdir(parents=True, exist_ok=True)
        video_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote dry-run video manifest: {video_manifest}")
        return

    subprocess.run(command, check=True)

    manifest["output"].update({
        "sha256": sha256_file(output),
        "bytes": output.stat().st_size,
        "probe": ffprobe_metadata(output),
    })
    video_manifest.parent.mkdir(parents=True, exist_ok=True)
    video_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote video manifest: {video_manifest}")


if __name__ == "__main__":
    main()
