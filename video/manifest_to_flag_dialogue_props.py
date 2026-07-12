#!/usr/bin/env python3
"""Create Remotion FlagDialogue props from a completed lesson manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

DEFAULT_TEACHER_FLAG = Path("video/country_flags/Flag_of_Peoples_Republic_of_China_Flat_Round-512x512.png")
DEFAULT_TARGET_FLAG = Path("video/country_flags/Flag_of_United_States_Flat_Round-512x512.png")
DEFAULT_GERMANY_FLAG = Path("video/country_flags/Flag_of_Germany_Flat_Round-512x512.png")
PUBLIC_RENDER_ASSETS = Path("public/render-assets")
DEFAULT_VISUAL_PROPS: dict[str, Any] = {
    "backgroundColor": "#ffffff",
    "flagSize": 132,
    "flagGap": 34,
    "haloMaxScale": 2.3,
    "haloMinScale": 1.45,
    "haloGain": 22,
    "haloSmoothFrames": 18,
    "haloFadeSeconds": 0.32,
    "haloVolumeThreshold": 0.012,
    "haloNormalizationOffset": 0.04,
    "haloNormalizationRange": 0.74,
    "haloMinVisibleVolume": 0,
    "haloVolumePower": 0.82,
    "haloMinOpacity": 0.42,
    "haloOpacityRange": 0.06,
    "haloBlobPoints": 72,
    "haloBlobBaseRadius": 72,
    "haloBlobVarianceBase": 0.5,
    "haloBlobVarianceVolume": 0.75,
    "haloBlobMotionDivisor": 30,
    "haloBlurStdDeviation": 3,
    "haloBlurOpacity": 0.04,
    "haloGradientRadius": 76,
    "haloGradientInnerColor": "#777777",
    "haloGradientInnerOpacity": 1,
    "haloGradientMidColor": "#777777",
    "haloGradientMidOffset": 84,
    "haloGradientMidOpacity": 1,
    "haloGradientOuterColor": "#777777",
    "haloGradientOuterOpacity": 0,
    "haloGradientFillOpacity": 1,
    "lineY": 540,
    "flagsLeft": 250,
    "textLeft": 660,
    "textWidth": 1010,
    "chineseTextFontSize": 48,
    "defaultTextFontSize": 52,
    "textFontWeight": 700,
    "chineseTextLineHeight": 1.22,
    "defaultTextLineHeight": 1.14,
    "activeFlagShadow": "0 12px 34px rgba(0, 0, 0, 0.18)",
    "inactiveFlagShadow": "0 8px 22px rgba(0, 0, 0, 0.10)",
    "renderAudio": True,
}
CP1252_REVERSE = {
    "\u20ac": 0x80,
    "\u201a": 0x82,
    "\u0192": 0x83,
    "\u201e": 0x84,
    "\u2026": 0x85,
    "\u2020": 0x86,
    "\u2021": 0x87,
    "\u02c6": 0x88,
    "\u2030": 0x89,
    "\u0160": 0x8A,
    "\u2039": 0x8B,
    "\u0152": 0x8C,
    "\u017d": 0x8E,
    "\u2018": 0x91,
    "\u2019": 0x92,
    "\u201c": 0x93,
    "\u201d": 0x94,
    "\u2022": 0x95,
    "\u2013": 0x96,
    "\u2014": 0x97,
    "\u02dc": 0x98,
    "\u2122": 0x99,
    "\u0161": 0x9A,
    "\u203a": 0x9B,
    "\u0153": 0x9C,
    "\u017e": 0x9E,
    "\u0178": 0x9F,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_public_asset(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Asset file not found: {path}")

    digest = sha256_file(path)[:16]
    suffix = path.suffix or ".bin"
    PUBLIC_RENDER_ASSETS.mkdir(parents=True, exist_ok=True)
    target = PUBLIC_RENDER_ASSETS / f"{path.stem}-{digest}{suffix}"

    if not target.exists() or target.stat().st_size != path.stat().st_size:
        shutil.copy2(path, target)

    return target.relative_to("public").as_posix()


def resolve_flag_path(path: Path) -> Path:
    if path.exists():
        return path

    flag_aliases = {
        "china": DEFAULT_TEACHER_FLAG,
        "cn": DEFAULT_TEACHER_FLAG,
        "prc": DEFAULT_TEACHER_FLAG,
        "us": DEFAULT_TARGET_FLAG,
        "usa": DEFAULT_TARGET_FLAG,
        "united-states": DEFAULT_TARGET_FLAG,
        "united_states": DEFAULT_TARGET_FLAG,
        "germany": DEFAULT_GERMANY_FLAG,
        "de": DEFAULT_GERMANY_FLAG,
    }
    alias = flag_aliases.get(path.stem.lower())
    if alias is not None and alias.exists():
        return alias

    return path


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
        reconstructed = bytearray()
        for char in text:
            codepoint = ord(char)
            if char in CP1252_REVERSE:
                reconstructed.append(CP1252_REVERSE[char])
            elif codepoint <= 0xFF:
                reconstructed.append(codepoint)
            else:
                return text
        try:
            repaired = bytes(reconstructed).decode("utf-8")
        except UnicodeError:
            return text

    if re.search(r"[\u4e00-\u9fff]", repaired) and not re.search(r"[\u4e00-\u9fff]", text):
        return repaired
    mojibake_markers = ("Ãƒ", "Ã¤", "Ã¥", "Ã§", "Ã¨", "Ã©", "Ã¦", "Ã¯", "ç¬", "è¯")
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

        entries.append({
            "start": round(max(start, preview_start) - preview_start, 6),
            "end": round(min(display_end, preview_end) - preview_start, 6),
            "lang": str(segment.get("language_code") or "auto"),
            "text": text,
        })

    if not entries:
        raise ValueError("No subtitle entries overlap the requested preview range.")

    return entries


def manifest_duration(manifest: dict[str, Any], segments: list[dict[str, Any]]) -> float:
    return float(
        manifest.get("summary", {}).get("duration_seconds")
        or manifest.get("summary", {}).get("final_output_duration_seconds")
        or segments[-1]["end_seconds"]
    )


def default_audio_src(manifest_path: Path, manifest: dict[str, Any]) -> str:
    sibling_candidates = [manifest_path.with_suffix(".mp3")]
    if manifest_path.name.endswith(".manifest.json"):
        sibling_candidates.insert(
            0,
            manifest_path.with_name(manifest_path.name.removesuffix(".manifest.json") + ".mp3"),
        )

    for sibling_mp3 in sibling_candidates:
        if sibling_mp3.exists():
            return str(sibling_mp3.resolve())

    output_path = manifest.get("output", {}).get("path") or manifest.get("output_path")
    if output_path:
        path = Path(str(output_path))
        candidates = [
            path if path.is_absolute() else (Path.cwd() / path),
            path if path.is_absolute() else (manifest_path.parent / path),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate.resolve())

    return str(manifest_path.with_suffix(".mp3").resolve())


def kebab_case(name: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"-\1", name).lower()


def add_visual_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("FlagDialogue visual options")
    for key, default in DEFAULT_VISUAL_PROPS.items():
        if isinstance(default, bool):
            continue
        value_type = str if isinstance(default, str) else type(default)
        group.add_argument(
            f"--{kebab_case(key)}",
            dest=key,
            type=value_type,
            default=default,
            help=f"Default: {default!r}",
        )
    group.add_argument(
        "--no-render-audio",
        dest="renderAudio",
        action="store_false",
        default=DEFAULT_VISUAL_PROPS["renderAudio"],
        help="Set renderAudio to false in generated props.",
    )


def parse_hex_color(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if match is None:
        return None
    hex_value = match.group(1)
    return (
        int(hex_value[0:2], 16),
        int(hex_value[2:4], 16),
        int(hex_value[4:6], 16),
    )


def blended_luminance(color: tuple[int, int, int], alpha: float) -> float:
    blended = [channel * alpha + 255 * (1 - alpha) for channel in color]
    return sum(blended) / 3


def warn_if_halo_is_likely_invisible(args: argparse.Namespace) -> None:
    max_center_alpha = (
        (args.haloMinOpacity + args.haloOpacityRange)
        * args.haloGradientInnerOpacity
        * args.haloGradientFillOpacity
    )
    min_center_alpha = (
        args.haloMinOpacity
        * args.haloGradientInnerOpacity
        * args.haloGradientFillOpacity
    )
    if max_center_alpha < 0.08:
        print(
            "Warning: halo opacity settings are likely too transparent to see on white. "
            f"Center alpha range is about {min_center_alpha:.3f}-{max_center_alpha:.3f}. "
            "For a visible solid center with faded edges, keep "
            "--halo-gradient-inner-opacity and --halo-gradient-fill-opacity near 1, "
            "then tune --halo-min-opacity / --halo-opacity-range."
        )
        return

    inner_color = parse_hex_color(args.haloGradientInnerColor)
    if inner_color is None:
        return

    max_luminance = blended_luminance(inner_color, max_center_alpha)
    min_luminance = blended_luminance(inner_color, min_center_alpha)
    if max_luminance > 226:
        print(
            "Warning: halo center is likely too close to white to see clearly. "
            f"Blended center brightness is about {min_luminance:.0f}-{max_luminance:.0f} "
            "on a 0-255 scale. Use a darker --halo-gradient-inner-color, for example "
            "#767676 or #5f5f5f."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Remotion FlagDialogue props from a completed lesson manifest."
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        help="Completed .manifest.json file. Can also be passed with --manifest.",
    )
    parser.add_argument(
        "--manifest",
        dest="manifest_option",
        type=Path,
        help="Completed .manifest.json file.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output props JSON path.")
    parser.add_argument("--audio-src", "--audio", dest="audio_src", default=None, help="Audio source for Remotion.")
    parser.add_argument("--teacher-language", default="zh")
    parser.add_argument("--target-language", default="en")
    parser.add_argument(
        "--teacher-flag-src",
        "--teacher-flag",
        dest="teacher_flag_src",
        type=Path,
        default=DEFAULT_TEACHER_FLAG,
    )
    parser.add_argument(
        "--target-flag-src",
        "--target-flag",
        dest="target_flag_src",
        type=Path,
        default=DEFAULT_TARGET_FLAG,
    )
    parser.add_argument(
        "--no-stage-assets",
        action="store_true",
        help="Do not copy audio and flags into public/render-assets.",
    )
    parser.add_argument("--preview-start", type=float, default=0.0)
    parser.add_argument("--preview-duration", type=float, default=None)
    parser.add_argument("--still-frame", type=int, default=120)
    parser.add_argument(
        "--speech-only",
        action="store_true",
        help="End subtitle entries when speech ends instead of holding until the next speech block.",
    )
    add_visual_arguments(parser)
    args = parser.parse_args()
    args.manifest = args.manifest_option or args.manifest
    if args.manifest is None:
        parser.error("the following arguments are required: manifest or --manifest")
    args.teacher_flag_src = resolve_flag_path(args.teacher_flag_src)
    args.target_flag_src = resolve_flag_path(args.target_flag_src)

    if args.preview_start < 0:
        parser.error("--preview-start must be zero or greater.")
    if args.preview_duration is not None and args.preview_duration <= 0:
        parser.error("--preview-duration must be greater than zero.")
    if args.still_frame < 0:
        parser.error("--still-frame must be zero or greater.")
    warn_if_halo_is_likely_invisible(args)
    for label, path in (
        ("Manifest", args.manifest),
        ("Teacher flag", args.teacher_flag_src),
        ("Target flag", args.target_flag_src),
    ):
        if not path.exists():
            parser.error(f"{label} file not found: {path}")

    try:
        manifest = load_json(args.manifest)
        segments = speech_segments(manifest)
        total_duration = manifest_duration(manifest, segments)
        preview_duration = args.preview_duration or max(0.0, total_duration - args.preview_start)
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

    audio_src = args.audio_src or default_audio_src(args.manifest, manifest)
    teacher_flag_src = str(args.teacher_flag_src.resolve())
    target_flag_src = str(args.target_flag_src.resolve())

    if not args.no_stage_assets:
        audio_src = stage_public_asset(Path(audio_src))
        teacher_flag_src = stage_public_asset(args.teacher_flag_src)
        target_flag_src = stage_public_asset(args.target_flag_src)

    visual_props = {
        key: getattr(args, key)
        for key in DEFAULT_VISUAL_PROPS
    }

    props = {
        "audioSrc": audio_src,
        "teacherFlagSrc": teacher_flag_src,
        "targetFlagSrc": target_flag_src,
        "teacherLanguage": args.teacher_language,
        "targetLanguage": args.target_language,
        "durationInSeconds": preview_duration,
        "subtitleEntries": entries,
        "frame": args.still_frame,
    }
    props.update(visual_props)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(props, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote FlagDialogue props: {args.output}")
    print(f"Subtitle entries: {len(entries)}")
    print(f"Duration seconds: {preview_duration:.3f}")


if __name__ == "__main__":
    main()
