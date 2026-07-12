#!/usr/bin/env python3
"""Create Remotion PodcastFinal props from a completed lesson manifest."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

DEFAULT_STYLE_PROPS = Path(__file__).with_name("remotion") / "ribbon-theme-final-props.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def remove_comment_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: remove_comment_keys(item)
            for key, item in value.items()
            if not key.startswith("_")
        }
    if isinstance(value, list):
        return [remove_comment_keys(item) for item in value]
    return value


def speech_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    missing_timings = False

    for segment in manifest.get("segments", []):
        if segment.get("type") != "speech":
            continue
        if "start_seconds" not in segment or "end_seconds" not in segment:
            missing_timings = True
            continue
        segments.append(segment)

    if missing_timings:
        raise ValueError(
            "Manifest contains speech segments without timings. Generate the MP3 first; "
            "dry-run manifests cannot drive Remotion subtitles."
        )
    if not segments:
        raise ValueError("Manifest contains no timed speech segments.")

    return segments


def repair_mojibake(text: str) -> str:
    try:
        repaired = text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return text

    mojibake_markers = ("Ã", "ä", "å", "ç", "è", "é", "æ", "ï")
    if any(marker in text for marker in mojibake_markers):
        return repaired
    return text


def build_subtitle_entries(
    segments: list[dict[str, Any]],
    preview_start: float,
    preview_duration: float,
    hold_until_next: bool,
) -> list[dict[str, Any]]:
    preview_end = preview_start + preview_duration
    entries: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        start = float(segment["start_seconds"])
        speech_end = float(segment["end_seconds"])
        next_start = (
            float(segments[index + 1]["start_seconds"])
            if index + 1 < len(segments)
            else speech_end
        )
        display_end = next_start if hold_until_next else speech_end

        if display_end <= preview_start or start >= preview_end:
            continue

        text = repair_mojibake(str(segment.get("text", ""))).strip()
        if not text:
            continue

        entries.append(
            {
                "start": round(max(start, preview_start) - preview_start, 6),
                "end": round(min(display_end, preview_end) - preview_start, 6),
                "lang": str(segment.get("language_code") or "auto"),
                "text": text,
            }
        )

    if not entries:
        raise ValueError("No subtitle entries overlap the requested preview range.")

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Remotion PodcastFinal props from a completed lesson manifest."
    )
    parser.add_argument("manifest", type=Path, help="Completed .manifest.json file.")
    parser.add_argument("--output", type=Path, required=True, help="Output props JSON path.")
    parser.add_argument(
        "--audio-src",
        default="demo-audio.mp3",
        help="Audio source as Remotion should load it, usually a file in public/.",
    )
    parser.add_argument(
        "--style-props",
        type=Path,
        default=DEFAULT_STYLE_PROPS,
        help=(
            "Reusable PodcastFinal style props JSON. May contain a top-level waveform "
            "object or any other PodcastFinal props to merge into the generated file."
        ),
    )
    parser.add_argument("--preview-start", type=float, default=0.0)
    parser.add_argument(
        "--preview-duration",
        type=float,
        default=None,
        help="Duration in seconds. Defaults to the remaining manifest duration.",
    )
    parser.add_argument(
        "--speech-only",
        action="store_true",
        help="End subtitle entries when speech ends instead of holding until the next speech block.",
    )
    args = parser.parse_args()

    if args.preview_start < 0:
        parser.error("--preview-start must be zero or greater.")
    if args.preview_duration is not None and args.preview_duration <= 0:
        parser.error("--preview-duration must be greater than zero.")
    if not args.manifest.exists():
        parser.error(f"Manifest not found: {args.manifest}")
    if not args.style_props.exists():
        parser.error(f"Style props file not found: {args.style_props}")

    try:
        manifest = load_json(args.manifest)
        style_props = remove_comment_keys(load_json(args.style_props))
        segments = speech_segments(manifest)
        manifest_duration = float(
            manifest.get("summary", {}).get("duration_seconds")
            or manifest.get("summary", {}).get("final_output_duration_seconds")
            or segments[-1]["end_seconds"]
        )
        preview_duration = args.preview_duration or max(
            0.0,
            manifest_duration - args.preview_start,
        )
        if preview_duration <= 0:
            raise ValueError("Preview range does not overlap the manifest duration.")
        entries = build_subtitle_entries(
            segments=segments,
            preview_start=args.preview_start,
            preview_duration=preview_duration,
            hold_until_next=not args.speech_only,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    props = copy.deepcopy(style_props)
    props.update({
        "audioSrc": args.audio_src,
        "durationInSeconds": preview_duration,
        "subtitleEntries": entries,
    })
    if "waveform" not in props:
        parser.error(f"Style props file must define a waveform object: {args.style_props}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(props, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote Remotion props: {args.output}")
    print(f"Subtitle entries: {len(entries)}")


if __name__ == "__main__":
    main()
