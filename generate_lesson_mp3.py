#!/usr/bin/env python3
"""
Segmented ElevenLabs TTS generator with explicit <lang code="..."/> tags.

Supported tags inside lesson .txt files:
    <lang code="en" />
    <lang code="zh" />
    <lang code="de-DE" />
    <lang code="auto" />
    <break time="3.0s" />

Rules:
- <lang code="..."/> is metadata. It is removed before text is sent to ElevenLabs.
- The language tag applies to the next spoken text block until the next <break .../>
  tag or next <lang .../> tag.
- <break time="..."/> is converted into local silence using FFmpeg.
- If a spoken text block has no explicit language tag, the script falls back to
  conservative auto-detection:
    Chinese characters only -> zh
    Latin letters only      -> en
    mixed/unclear           -> no language_code
- Exact-text caching is preserved. Identical text including punctuation/capitalization,
  plus identical language_code and TTS settings, reuses cached audio.

Recommended model:
- eleven_multilingual_v2

Requirements:
    pip install requests

Windows PowerShell setup:
    $env:ELEVENLABS_API_KEY = "your_api_key"
    $env:Path += ";C:\ffmpeg\bin"

Example:
    python generate_lesson_mp3.py `
      lesson01.txt `
      --voice-id YOUR_VOICE_ID `
      --model-id eleven_multilingual_v2 `
      --output lesson01.mp3 `
      --max-chars 350 `
      --speech-tempo 0.88 `
      --break-multiplier 1.25

Useful options:
    --default-language de
    --disable-language-code
    --keep-work
    --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
AUTO_LANGUAGE_CODE = "auto"

BREAK_RE = re.compile(
    r'<break\s+time=["\']([0-9]+(?:\.[0-9]+)?)s["\']\s*/>',
    flags=re.IGNORECASE,
)

LANG_RE = re.compile(
    r'<lang\s+code=["\'](auto|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)["\']\s*/>',
    flags=re.IGNORECASE,
)

TAG_RE = re.compile(
    r'(<break\s+time=["\'][0-9]+(?:\.[0-9]+)?s["\']\s*/>|<lang\s+code=["\'](?:auto|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)["\']\s*/>)',
    flags=re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_git_metadata() -> dict[str, Any] | None:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return {"commit": commit, "dirty": bool(status.strip())}


def get_api_key() -> str:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing ELEVENLABS_API_KEY environment variable.")
    return api_key


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    fallback = r"C:\ffmpeg\bin\ffmpeg.exe"
    if Path(fallback).exists():
        return fallback

    raise FileNotFoundError(
        "Could not find ffmpeg. Add it to PATH or place it at C:\\ffmpeg\\bin\\ffmpeg.exe"
    )


def find_ffprobe(ffmpeg: str) -> str:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe

    ffmpeg_path = Path(ffmpeg)
    sibling = ffmpeg_path.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if sibling.exists():
        return str(sibling)

    fallback = r"C:\ffmpeg\bin\ffprobe.exe"
    if Path(fallback).exists():
        return fallback

    raise FileNotFoundError(
        "Could not find ffprobe. Add it to PATH or place it next to ffmpeg."
    )


def run_command(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n\nSTDOUT:\n"
            + result.stdout
            + "\n\nSTDERR:\n"
            + result.stderr
        )


def run_command_capture(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n\nSTDOUT:\n"
            + result.stdout
            + "\n\nSTDERR:\n"
            + result.stderr
        )
    return result.stdout


def get_audio_duration_seconds(ffprobe: str, audio_path: Path) -> float:
    output = run_command_capture([
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ])
    return float(output.strip())


def normalize_language_code(code: str) -> str:
    """
    Normalizes BCP-47-style language codes for API use and cache stability.

    Examples:
    - EN -> en
    - zh-cn -> zh-CN
    - de-de -> de-DE
    - pt-br -> pt-BR
    """
    parts = code.strip().split("-")
    if not parts or not parts[0]:
        raise ValueError("Empty language code.")

    first = parts[0].lower()
    rest = []

    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            rest.append(part.upper())
        elif len(part) == 4 and part.isalpha():
            rest.append(part.title())
        else:
            rest.append(part)

    return "-".join([first] + rest)


def normalize_tag_language_code(code: str) -> str:
    normalized = code.strip().lower()
    if normalized == AUTO_LANGUAGE_CODE:
        return AUTO_LANGUAGE_CODE
    return normalize_language_code(code)


def language_matches_role(language_code: str | None, role_language: str | None) -> bool:
    if not language_code or not role_language:
        return False
    if "-" in role_language:
        return language_code == role_language
    return language_code.split("-", 1)[0] == role_language


def speech_tempo_for_language(language_code: str | None, args: argparse.Namespace) -> float:
    if language_matches_role(language_code, args.teacher_language):
        return args.teacher_speech_tempo
    if language_matches_role(language_code, args.target_language):
        return args.target_speech_tempo
    return args.speech_tempo


def configure_console_output() -> None:
    """
    Make dry-run/status output reliable on Windows consoles that default to cp1252.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def detect_language_code(text: str) -> str | None:
    """
    Conservative fallback detector for untagged snippets.

    Returns:
    - "zh" for Chinese-only snippets
    - "en" for Latin-only snippets
    - None for mixed or unclear snippets

    For German, French, Spanish, etc., use explicit <lang code="de" />,
    <lang code="fr" />, <lang code="es" /> tags. Auto-detection cannot reliably
    distinguish Latin-script languages.
    """
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))

    if chinese_chars > 0 and latin_chars == 0:
        return "zh"

    if latin_chars > 0 and chinese_chars == 0:
        return "en"

    return None


def parse_tts_script(script_text: str) -> list[dict[str, Any]]:
    """
    Converts a tagged transcript into ordered segments:
    - {"type": "speech", "text": "...", "language_code": "en"}
    - {"type": "silence", "seconds": 3.0}

    Language tag behavior:
    - <lang code="de" /> applies to the next spoken block.
    - It remains in effect until the next <break .../> or <lang .../> tag.
    - Breaks clear the current language for the next block unless another
      <lang .../> tag appears.

    This matches the production-script rule:
    "The language tag applies to the next spoken text block until the next
    <break time='...' /> tag or the next <lang code='...' /> tag."

    The <lang .../> tags are not included in the spoken text.
    """
    segments: list[dict[str, Any]] = []
    current_lang: str | None = None
    pos = 0

    for match in TAG_RE.finditer(script_text):
        before = script_text[pos:match.start()].strip()
        if before:
            segments.append({
                "type": "speech",
                "text": before,
                "language_code": current_lang,
            })

        tag = match.group(0).strip()

        lang_match = LANG_RE.fullmatch(tag)
        if lang_match:
            current_lang = normalize_tag_language_code(lang_match.group(1))
            pos = match.end()
            continue

        break_match = BREAK_RE.fullmatch(tag)
        if break_match:
            seconds = float(break_match.group(1))
            if seconds > 0:
                segments.append({"type": "silence", "seconds": seconds})
            current_lang = None
            pos = match.end()
            continue

        pos = match.end()

    after = script_text[pos:].strip()
    if after:
        segments.append({
            "type": "speech",
            "text": after,
            "language_code": current_lang,
        })

    return segments


def split_long_speech(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    chunks: list[str] = []
    current = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        candidate = (current + "\n" + part).strip() if current else part

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(part) <= max_chars:
            current = part
        else:
            for i in range(0, len(part), max_chars):
                chunks.append(part[i : i + max_chars])
            current = ""

    if current:
        chunks.append(current)

    return chunks


def normalise_segments(
    segments: list[dict[str, Any]],
    max_chars: int,
    default_language: str | None = None,
    disable_language_code: bool = False,
) -> list[dict[str, Any]]:
    """
    Splits only overlong speech segments and removes empty segments.
    Does not normalize punctuation/case.

    For speech segments:
    - Explicit tag language wins unless it is "auto".
    - Explicit "auto" leaves language_code unset for mixed-language blocks.
    - If no explicit tag and default_language is set, use default_language.
    - If neither, fallback detect_language_code(text).
    - If disable_language_code is True, always use None.
    """
    output: list[dict[str, Any]] = []

    if default_language:
        default_language = normalize_language_code(default_language)

    for segment in segments:
        if segment["type"] == "silence":
            seconds = float(segment["seconds"])
            if seconds > 0:
                output.append({"type": "silence", "seconds": seconds})
            continue

        text = segment["text"].strip()
        if not text:
            continue

        explicit_language = segment.get("language_code")

        if disable_language_code:
            language_code = None
        elif explicit_language == AUTO_LANGUAGE_CODE:
            language_code = None
        elif explicit_language:
            language_code = normalize_language_code(explicit_language)
        elif default_language:
            language_code = default_language
        else:
            language_code = detect_language_code(text)

        for chunk in split_long_speech(text, max_chars=max_chars):
            output.append({
                "type": "speech",
                "text": chunk.strip(),
                "language_code": language_code,
            })

    return output


def cache_key_for_speech(
    *,
    text: str,
    voice_id: str,
    model_id: str,
    output_format: str,
    stability: float,
    similarity_boost: float,
    style: float,
    use_speaker_boost: bool,
    seed: int | None,
    language_code: str | None,
) -> str:
    data = {
        "text": text,
        "voice_id": voice_id,
        "model_id": model_id,
        "output_format": output_format,
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": style,
        "use_speaker_boost": use_speaker_boost,
        "seed": seed,
        "language_code": language_code,
    }
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_manifest(
    *,
    input_path: Path,
    output_path: Path,
    manifest_path: Path,
    segments: list[dict[str, Any]],
    args: argparse.Namespace,
    lang_counts: dict[str, int],
) -> dict[str, Any]:
    manifest_segments: list[dict[str, Any]] = []
    generator_path = Path(__file__).resolve()

    for index, segment in enumerate(segments, start=1):
        if segment["type"] == "speech":
            text = segment["text"]
            language_code = segment.get("language_code")
            cache_key = cache_key_for_speech(
                text=text,
                voice_id=args.voice_id,
                model_id=args.model_id,
                output_format=args.output_format,
                stability=args.stability,
                similarity_boost=args.similarity_boost,
                style=args.style,
                use_speaker_boost=not args.no_speaker_boost,
                seed=args.seed,
                language_code=language_code,
            )
            manifest_segments.append({
                "index": index,
                "type": "speech",
                "language_code": language_code,
                "text": text,
                "character_count": len(text),
                "speech_tempo": speech_tempo_for_language(language_code, args),
                "cache_key": cache_key,
                "raw_audio_path": str(args.cache_dir / f"{cache_key}.mp3"),
            })
            continue

        seconds = float(segment["seconds"])
        rendered_seconds = max(args.min_break, seconds * args.break_multiplier)
        manifest_segments.append({
            "index": index,
            "type": "silence",
            "seconds": rendered_seconds,
            "source_seconds": seconds,
        })

    return {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": {
            "path": str(generator_path),
            "sha256": sha256_file(generator_path),
            "command": [sys.executable, *sys.argv],
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "requests_version": requests.__version__,
        },
        "git": get_git_metadata(),
        "source": {
            "path": str(input_path),
            "sha256": sha256_file(input_path),
        },
        "input_path": str(input_path),
        "output_path": str(output_path),
        "manifest_path": str(manifest_path),
        "mode": "dry_run" if args.dry_run else "synthesis",
        "tts_settings": {
            "provider": "ElevenLabs",
            "model_id": args.model_id,
            "voice_id": args.voice_id,
            "output_format": args.output_format,
            "stability": args.stability,
            "similarity_boost": args.similarity_boost,
            "style": args.style,
            "use_speaker_boost": not args.no_speaker_boost,
            "seed": args.seed,
        },
        "processing_settings": {
            "bitrate": args.bitrate,
            "max_chars": args.max_chars,
            "speech_tempo": args.speech_tempo,
            "teacher_language": args.teacher_language,
            "teacher_speech_tempo": args.teacher_speech_tempo,
            "target_language": args.target_language,
            "target_speech_tempo": args.target_speech_tempo,
            "break_multiplier": args.break_multiplier,
            "min_break": args.min_break,
            "normalize_loudness": args.normalize_loudness,
            "loudness_target_i": args.loudness_target_i,
            "loudness_target_tp": args.loudness_target_tp,
            "loudness_target_lra": args.loudness_target_lra,
            "default_language": args.default_language,
            "disable_language_code": args.disable_language_code,
        },
        "workspace_settings": {
            "cache_dir": str(args.cache_dir),
            "work_dir": str(args.work_dir),
            "keep_work": args.keep_work,
            "sleep_between_api_calls": args.sleep,
        },
        "language_code_mode": "disabled" if args.disable_language_code else "explicit tags + fallback",
        "summary": {
            "segments": len(segments),
            "speech_segments": sum(1 for item in segments if item["type"] == "speech"),
            "silence_segments": sum(1 for item in segments if item["type"] == "silence"),
            "language_counts": lang_counts,
        },
        "segments": manifest_segments,
    }


def write_manifest(manifest: dict[str, Any], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def add_manifest_timings(
    *,
    manifest: dict[str, Any],
    segment_paths: list[Path],
    ffprobe: str,
) -> None:
    current_time = 0.0

    for segment, segment_path in zip(manifest["segments"], segment_paths):
        duration = get_audio_duration_seconds(ffprobe, segment_path)
        start_time = current_time
        end_time = start_time + duration

        segment["duration_seconds"] = round(duration, 6)
        segment["start_seconds"] = round(start_time, 6)
        segment["end_seconds"] = round(end_time, 6)

        current_time = end_time

    manifest["summary"]["duration_seconds"] = round(current_time, 6)
    manifest["summary"]["duration_minutes"] = round(current_time / 60.0, 3)


def call_elevenlabs_tts(
    *,
    api_key: str,
    voice_id: str,
    text: str,
    output_path: Path,
    model_id: str,
    output_format: str,
    stability: float,
    similarity_boost: float,
    style: float,
    use_speaker_boost: bool,
    seed: int | None,
    language_code: str | None,
    timeout: int = 120,
) -> None:
    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)

    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }

    params = {"output_format": output_format}

    payload: dict[str, Any] = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
        },
    }

    if seed is not None:
        payload["seed"] = seed

    if language_code:
        payload["language_code"] = language_code

    response = requests.post(
        url,
        headers=headers,
        params=params,
        json=payload,
        timeout=timeout,
    )

    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs API error {response.status_code}:\n{response.text}")

    output_path.write_bytes(response.content)


def make_silence_mp3(
    *,
    ffmpeg: str,
    seconds: float,
    output_path: Path,
    sample_rate: int = 44100,
    bitrate: str = "128k",
) -> None:
    command = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r={sample_rate}:cl=mono",
        "-t",
        f"{seconds:.3f}",
        "-acodec",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(output_path),
    ]
    run_command(command)


def slow_down_audio(
    *,
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    tempo: float,
    bitrate: str = "128k",
) -> None:
    if tempo <= 0:
        raise ValueError("Tempo must be greater than 0.")

    if abs(tempo - 1.0) < 0.001:
        shutil.copyfile(input_path, output_path)
        return

    filters: list[str] = []
    remaining = tempo

    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5

    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0

    filters.append(f"atempo={remaining:.5f}")
    filter_string = ",".join(filters)

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-filter:a",
        filter_string,
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(output_path),
    ]
    run_command(command)


def concat_mp3_files(
    *,
    ffmpeg: str,
    input_paths: list[Path],
    output_path: Path,
    bitrate: str = "128k",
) -> None:
    list_file = output_path.parent / f"{output_path.stem}_concat_list.txt"

    with list_file.open("w", encoding="utf-8") as f:
        for path in input_paths:
            f.write(f"file '{path.resolve().as_posix()}'\n")

    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-acodec",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(output_path),
    ]

    try:
        run_command(command)
    finally:
        list_file.unlink(missing_ok=True)


def normalize_loudness(
    *,
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    target_i: float,
    target_tp: float,
    target_lra: float,
    bitrate: str,
) -> None:
    temp_path = output_path.with_name(f"{output_path.stem}_normalized_tmp{output_path.suffix}")
    filter_value = f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-af",
        filter_value,
        "-ar",
        "44100",
        "-ac",
        "1",
        "-acodec",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(temp_path),
    ]

    try:
        run_command(command)
        try:
            temp_path.replace(output_path)
        except PermissionError:
            shutil.copyfile(temp_path, output_path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except PermissionError:
            pass


def main() -> None:
    configure_console_output()

    parser = argparse.ArgumentParser(
        description=(
            "Generate MP3 from a tagged TTS transcript using segmented ElevenLabs requests, "
            "explicit <lang code=\"...\"/> tags, exact cache, local silence, and FFmpeg stitching."
        )
    )

    parser.add_argument("input_txt", type=Path)
    parser.add_argument("--voice-id", required=True)
    parser.add_argument("--output", type=Path, default=None)

    parser.add_argument("--model-id", default="eleven_multilingual_v2")
    parser.add_argument("--output-format", default="mp3_44100_128")
    parser.add_argument("--bitrate", default="128k")

    parser.add_argument(
        "--max-chars",
        type=int,
        default=350,
        help="Maximum characters per ElevenLabs request. Smaller values reduce voice drift.",
    )

    parser.add_argument("--stability", type=float, default=0.65)
    parser.add_argument("--similarity-boost", type=float, default=0.80)
    parser.add_argument("--style", type=float, default=0.0)
    parser.add_argument("--no-speaker-boost", action="store_true")

    parser.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="Best-effort deterministic seed. Use --seed -1 to omit seed.",
    )

    parser.add_argument(
        "--speech-tempo",
        type=float,
        default=0.90,
        help="Fallback tempo for speech not matched to a teacher or target language.",
    )

    parser.add_argument(
        "--teacher-language",
        default=None,
        help="Language code spoken by the narrator/teacher, e.g. zh or en.",
    )

    parser.add_argument(
        "--teacher-speech-tempo",
        type=float,
        default=None,
        help="Tempo for --teacher-language. Defaults to --speech-tempo.",
    )

    parser.add_argument(
        "--target-language",
        default=None,
        help="Language code being taught, e.g. en or de.",
    )

    parser.add_argument(
        "--target-speech-tempo",
        type=float,
        default=None,
        help="Tempo for --target-language. Defaults to --speech-tempo.",
    )

    parser.add_argument(
        "--min-break",
        type=float,
        default=0.0,
        help="Minimum silence duration in seconds for every break tag.",
    )

    parser.add_argument(
        "--break-multiplier",
        type=float,
        default=1.0,
        help="Multiply every break duration. Example: 1.25 makes breaks 25 percent longer.",
    )

    parser.add_argument(
        "--normalize-loudness",
        action="store_true",
        help="Normalize the final MP3 with FFmpeg loudnorm after concatenation.",
    )

    parser.add_argument(
        "--loudness-target-i",
        type=float,
        default=-16.0,
        help="Integrated loudness target in LUFS for --normalize-loudness.",
    )

    parser.add_argument(
        "--loudness-target-tp",
        type=float,
        default=-1.5,
        help="True peak target in dBTP for --normalize-loudness.",
    )

    parser.add_argument(
        "--loudness-target-lra",
        type=float,
        default=11.0,
        help="Loudness range target for --normalize-loudness.",
    )

    parser.add_argument(
        "--default-language",
        default=None,
        help=(
            "Fallback language code for untagged speech blocks, e.g. en, zh, de, de-DE. "
            "Explicit <lang code=\"...\"/> tags still win."
        ),
    )

    parser.add_argument(
        "--disable-language-code",
        action="store_true",
        help="Do not send language_code at all. Useful for comparison tests.",
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("tts_cache"),
        help="Cache directory for generated speech snippets.",
    )

    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("tts_work"),
        help="Temporary working directory for processed segments.",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to wait between ElevenLabs API calls.",
    )

    parser.add_argument("--keep-work", action="store_true")

    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest JSON path. Defaults to output path with .manifest.json suffix.",
    )

    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Do not write a manifest JSON file.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print segment summary without calling ElevenLabs or FFmpeg.",
    )

    args = parser.parse_args()

    if args.seed == -1:
        args.seed = None

    if args.teacher_speech_tempo is not None and not args.teacher_language:
        parser.error("--teacher-speech-tempo requires --teacher-language")
    if args.target_speech_tempo is not None and not args.target_language:
        parser.error("--target-speech-tempo requires --target-language")

    if args.teacher_language:
        args.teacher_language = normalize_language_code(args.teacher_language)
    if args.target_language:
        args.target_language = normalize_language_code(args.target_language)
    if (
        args.teacher_language
        and args.target_language
        and (
            language_matches_role(args.teacher_language, args.target_language)
            or language_matches_role(args.target_language, args.teacher_language)
        )
    ):
        parser.error("--teacher-language and --target-language must not overlap")

    if args.teacher_speech_tempo is None:
        args.teacher_speech_tempo = args.speech_tempo
    if args.target_speech_tempo is None:
        args.target_speech_tempo = args.speech_tempo
    for option, tempo in (
        ("--speech-tempo", args.speech_tempo),
        ("--teacher-speech-tempo", args.teacher_speech_tempo),
        ("--target-speech-tempo", args.target_speech_tempo),
    ):
        if tempo <= 0:
            parser.error(f"{option} must be greater than zero")

    input_path = args.input_txt
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    script_text = input_path.read_text(encoding="utf-8")
    raw_segments = parse_tts_script(script_text)
    segments = normalise_segments(
        raw_segments,
        max_chars=args.max_chars,
        default_language=args.default_language,
        disable_language_code=args.disable_language_code,
    )

    output_path = args.output or input_path.with_suffix(".mp3")
    manifest_path = args.manifest or output_path.with_suffix(".manifest.json")

    lang_counts: dict[str, int] = {}
    for segment in segments:
        if segment["type"] == "speech":
            key = segment.get("language_code") or "none"
            lang_counts[key] = lang_counts.get(key, 0) + 1

    manifest = build_manifest(
        input_path=input_path,
        output_path=output_path,
        manifest_path=manifest_path,
        segments=segments,
        args=args,
        lang_counts=lang_counts,
    )

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Segments: {len(segments)}")
    print(f"Speech segments: {sum(1 for s in segments if s['type'] == 'speech')}")
    print(f"Silence segments: {sum(1 for s in segments if s['type'] == 'silence')}")
    print(f"Language counts: {lang_counts}")
    print(f"Language code mode: {'disabled' if args.disable_language_code else 'explicit tags + fallback'}")
    if not args.no_manifest:
        print(f"Manifest: {manifest_path}")

    if args.dry_run:
        print("\nDry run segment preview:")
        for i, segment in enumerate(segments[:50], start=1):
            if segment["type"] == "speech":
                preview = segment["text"].replace("\n", " ")
                if len(preview) > 90:
                    preview = preview[:87] + "..."
                language_code = segment.get("language_code")
                tempo = speech_tempo_for_language(language_code, args)
                print(
                    f"{i:04d} SPEECH lang={language_code or 'none'} tempo={tempo} "
                    f"chars={len(segment['text'])}: {preview}"
                )
            else:
                print(f"{i:04d} SILENCE {segment['seconds']:.2f}s")
        if len(segments) > 50:
            print(f"... {len(segments) - 50} more segments")
        if not args.no_manifest:
            write_manifest(manifest, manifest_path)
            print(f"Wrote manifest: {manifest_path}")
        return

    api_key = get_api_key()
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe(ffmpeg)

    args.cache_dir.mkdir(parents=True, exist_ok=True)

    lesson_work_dir = args.work_dir / output_path.stem
    if lesson_work_dir.exists():
        shutil.rmtree(lesson_work_dir, ignore_errors=True)
    lesson_work_dir.mkdir(parents=True, exist_ok=True)

    print(f"Model: {args.model_id}")
    print(f"Voice ID: {args.voice_id}")
    print(f"Fallback speech tempo: {args.speech_tempo}")
    if args.teacher_language:
        print(f"Teacher speech tempo: {args.teacher_language} = {args.teacher_speech_tempo}")
    if args.target_language:
        print(f"Target speech tempo: {args.target_language} = {args.target_speech_tempo}")
    print(f"Break multiplier: {args.break_multiplier}")
    print(f"Minimum break: {args.min_break}")
    print(f"Loudness normalization: {'on' if args.normalize_loudness else 'off'}")
    print(f"FFmpeg: {ffmpeg}")
    print(f"FFprobe: {ffprobe}")

    final_segment_files: list[Path] = []
    speech_count = 0
    silence_count = 0
    cache_hits = 0
    cache_misses = 0

    for index, segment in enumerate(segments, start=1):
        if segment["type"] == "speech":
            speech_count += 1
            text = segment["text"]
            language_code = segment.get("language_code")

            key = cache_key_for_speech(
                text=text,
                voice_id=args.voice_id,
                model_id=args.model_id,
                output_format=args.output_format,
                stability=args.stability,
                similarity_boost=args.similarity_boost,
                style=args.style,
                use_speaker_boost=not args.no_speaker_boost,
                seed=args.seed,
                language_code=language_code,
            )

            raw_speech_path = args.cache_dir / f"{key}.mp3"
            processed_path = lesson_work_dir / f"{index:05d}_speech.mp3"
            speech_tempo = speech_tempo_for_language(language_code, args)

            lang_note = language_code or "no-code"
            cache_hit = raw_speech_path.exists()

            if cache_hit:
                cache_hits += 1
                print(f"[{index}/{len(segments)}] speech cache HIT ({lang_note}): {len(text)} chars")
            else:
                cache_misses += 1
                print(f"[{index}/{len(segments)}] speech cache MISS ({lang_note}); generating: {len(text)} chars")
                call_elevenlabs_tts(
                    api_key=api_key,
                    voice_id=args.voice_id,
                    text=text,
                    output_path=raw_speech_path,
                    model_id=args.model_id,
                    output_format=args.output_format,
                    stability=args.stability,
                    similarity_boost=args.similarity_boost,
                    style=args.style,
                    use_speaker_boost=not args.no_speaker_boost,
                    seed=args.seed,
                    language_code=language_code,
                )
                time.sleep(args.sleep)

            slow_down_audio(
                ffmpeg=ffmpeg,
                input_path=raw_speech_path,
                output_path=processed_path,
                tempo=speech_tempo,
                bitrate=args.bitrate,
            )

            final_segment_files.append(processed_path)
            manifest["segments"][index - 1]["cache_hit"] = cache_hit
            manifest["segments"][index - 1]["processed_audio_path"] = str(processed_path)

        elif segment["type"] == "silence":
            silence_count += 1
            seconds = float(segment["seconds"])
            seconds = max(args.min_break, seconds * args.break_multiplier)

            silence_path = lesson_work_dir / f"{index:05d}_silence_{seconds:.2f}s.mp3"
            print(f"[{index}/{len(segments)}] silence: {seconds:.2f}s")

            make_silence_mp3(
                ffmpeg=ffmpeg,
                seconds=seconds,
                output_path=silence_path,
                bitrate=args.bitrate,
            )

            final_segment_files.append(silence_path)
            manifest["segments"][index - 1]["audio_path"] = str(silence_path)

    print(f"Speech segments: {speech_count}")
    print(f"Silence segments: {silence_count}")
    print(f"Cache hits: {cache_hits}")
    print(f"Cache misses: {cache_misses}")
    print("Concatenating final MP3...")

    concat_mp3_files(
        ffmpeg=ffmpeg,
        input_paths=final_segment_files,
        output_path=output_path,
        bitrate=args.bitrate,
    )

    if not output_path.exists():
        raise RuntimeError(f"Expected output file was not created: {output_path}")

    if not args.no_manifest:
        add_manifest_timings(
            manifest=manifest,
            segment_paths=final_segment_files,
            ffprobe=ffprobe,
        )
        manifest["summary"]["cache_hits"] = cache_hits
        manifest["summary"]["cache_misses"] = cache_misses
        manifest["summary"]["final_segment_files"] = [str(path) for path in final_segment_files]

    if args.normalize_loudness:
        print(
            "Normalizing loudness "
            f"(I={args.loudness_target_i}, TP={args.loudness_target_tp}, LRA={args.loudness_target_lra})..."
        )
        normalize_loudness(
            ffmpeg=ffmpeg,
            input_path=output_path,
            output_path=output_path,
            target_i=args.loudness_target_i,
            target_tp=args.loudness_target_tp,
            target_lra=args.loudness_target_lra,
            bitrate=args.bitrate,
        )

    if not args.no_manifest:
        manifest["summary"]["final_output_duration_seconds"] = round(
            get_audio_duration_seconds(ffprobe, output_path),
            6,
        )
        manifest["output"] = {
            "path": str(output_path),
            "sha256": sha256_file(output_path),
            "bytes": output_path.stat().st_size,
        }
        write_manifest(manifest, manifest_path)
        print(f"Wrote manifest: {manifest_path}")

    if not args.keep_work:
        shutil.rmtree(lesson_work_dir, ignore_errors=True)

    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
