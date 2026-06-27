#!/usr/bin/env python3
"""Generate standard SRT and flowing ASS subtitles from a completed lesson manifest."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).with_name("video_style.json")


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    language_code: str | None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cues(manifest: dict[str, Any], languages: set[str] | None) -> list[Cue]:
    cues: list[Cue] = []
    missing_timings = False

    for segment in manifest.get("segments", []):
        if segment.get("type") != "speech":
            continue
        if "start_seconds" not in segment or "end_seconds" not in segment:
            missing_timings = True
            continue

        language_code = segment.get("language_code")
        if languages and language_code not in languages:
            continue
        cues.append(Cue(
            start=float(segment["start_seconds"]),
            end=float(segment["end_seconds"]),
            text=str(segment["text"]).strip(),
            language_code=language_code,
        ))

    if missing_timings:
        raise ValueError(
            "The manifest contains speech segments without measured timings. "
            "Generate the lesson audio first; dry-run manifests cannot produce synchronized subtitles."
        )
    if not cues:
        raise ValueError("No timed speech segments matched the requested languages.")
    return cues


def srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def ass_color(value: str) -> str:
    match = re.fullmatch(r"#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?", value)
    if not match:
        raise ValueError(f"Invalid color {value!r}; expected #RRGGBB or #RRGGBBAA.")
    rgb, alpha = match.groups()
    red, green, blue = rgb[0:2], rgb[2:4], rgb[4:6]
    ass_alpha = f"{255 - int(alpha, 16):02X}" if alpha else "00"
    return f"&H{ass_alpha}{blue}{green}{red}"


def ass_text(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def write_srt(cues: list[Cue], output_path: Path, hold_until_next: bool) -> None:
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        end = cues[index].start if hold_until_next and index < len(cues) else cue.end
        blocks.append(
            f"{index}\n{srt_timestamp(cue.start)} --> {srt_timestamp(end)}\n{cue.text}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8-sig")


def style_line(name: str, settings: dict[str, Any], video: dict[str, Any]) -> str:
    return ",".join([
        name,
        settings["font"],
        str(settings["font_size"]),
        ass_color(settings["primary_color"]),
        ass_color(settings.get("secondary_color", settings["primary_color"])),
        ass_color(settings["outline_color"]),
        ass_color(settings["background_color"]),
        "-1" if settings.get("bold", False) else "0",
        "0",
        "0",
        "0",
        "100",
        "100",
        "0",
        "0",
        str(settings.get("border_style", 1)),
        str(settings.get("outline_width", 2)),
        str(settings.get("shadow", 0)),
        "5",
        "0",
        "0",
        "0",
        "1",
    ])


def dialogue(start: float, end: float, style: str, overrides: str, text: str) -> str | None:
    if end - start < 0.01:
        return None
    return (
        f"Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},{style},,0,0,0,,"
        f"{{{overrides}}}{ass_text(text)}"
    )


def write_ass(cues: list[Cue], output_path: Path, config: dict[str, Any]) -> None:
    video = config["video"]
    area = config["subtitle_area"]
    text_config = config["text"]
    animation = config["animation"]
    active = text_config["active"]
    inactive = text_config["inactive"]

    left, top = int(area["left"]), int(area["top"])
    right, bottom = int(area["right"]), int(area["bottom"])
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    line_height = int(text_config["line_height"])
    before = int(animation["visible_lines_before"])
    after = int(animation["visible_lines_after"])
    transition_seconds = float(animation["transition_seconds"])
    clip = f"\\clip({left},{top},{right},{bottom})"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video["width"]}
PlayResY: {video["height"]}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: {style_line("Active", active, video)}
Style: {style_line("Inactive", inactive, video)}

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events: list[str] = []

    for index, cue in enumerate(cues):
        display_end = cues[index + 1].start if index + 1 < len(cues) else cue.end
        interval = max(0.0, display_end - cue.start)
        transition = min(transition_seconds, interval / 2) if index + 1 < len(cues) else 0.0
        transition_start = display_end - transition
        first = max(0, index - before)
        last = min(len(cues) - 1, index + after)

        for visible_index in range(first, last + 1):
            y = center_y + (visible_index - index) * line_height
            style = "Active" if visible_index == index else "Inactive"
            hold_overrides = f"\\an5\\pos({center_x},{y}){clip}"
            hold = dialogue(cue.start, transition_start, style, hold_overrides, cues[visible_index].text)
            if hold:
                events.append(hold)

            if transition > 0:
                move_overrides = (
                    f"\\an5\\move({center_x},{y},{center_x},{y - line_height},0,"
                    f"{round(transition * 1000)}){clip}"
                )
                move = dialogue(
                    transition_start,
                    display_end,
                    style,
                    move_overrides,
                    cues[visible_index].text,
                )
                if move:
                    events.append(move)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate standard SRT and flowing styled ASS subtitles from a completed lesson manifest."
    )
    parser.add_argument("manifest", type=Path, help="Completed lesson .manifest.json file.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Video/subtitle style JSON.")
    parser.add_argument("--srt-output", type=Path, default=None)
    parser.add_argument("--ass-output", type=Path, default=None)
    parser.add_argument(
        "--languages",
        nargs="+",
        default=None,
        help="Include only exact language codes, e.g. --languages en de.",
    )
    parser.add_argument(
        "--srt-speech-only",
        action="store_true",
        help="End SRT cues when speech ends instead of holding them until the next speech block.",
    )
    parser.add_argument("--no-srt", action="store_true")
    parser.add_argument("--no-ass", action="store_true")
    args = parser.parse_args()

    if args.no_srt and args.no_ass:
        parser.error("At least one output format must be enabled.")
    if not args.manifest.exists():
        parser.error(f"Manifest not found: {args.manifest}")
    if not args.config.exists():
        parser.error(f"Config not found: {args.config}")

    try:
        manifest = load_json(args.manifest)
        config = load_json(args.config)
        cues = load_cues(manifest, set(args.languages) if args.languages else None)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    base = args.manifest
    if base.name.endswith(".manifest.json"):
        base = base.with_name(base.name.removesuffix(".manifest.json"))
    else:
        base = base.with_suffix("")
    srt_output = args.srt_output or base.with_suffix(".srt")
    ass_output = args.ass_output or base.with_suffix(".ass")

    if not args.no_srt:
        write_srt(cues, srt_output, hold_until_next=not args.srt_speech_only)
        print(f"Wrote SRT: {srt_output}")
    if not args.no_ass:
        write_ass(cues, ass_output, config)
        print(f"Wrote flowing ASS: {ass_output}")
    print(f"Speech cues: {len(cues)}")


if __name__ == "__main__":
    main()
