#!/usr/bin/env python3
"""
Segmented ElevenLabs TTS generator with automatic language_code.

Purpose:
- Avoid long-script voice drift by synthesizing small snippets.
- Avoid standalone English word mispronunciation in Eleven Multilingual v2 by sending
  language_code="en" for English-only snippets and language_code="zh" for Chinese-only snippets.
- Create breaks locally with FFmpeg.
- Slow spoken audio only, not silence.
- Cache exact snippets. Identical text, including punctuation/capitalization, is reused.

Recommended model:
- eleven_multilingual_v2

Requirements:
    pip install requests

Windows PowerShell setup:
    $env:ELEVENLABS_API_KEY = "your_api_key"
    $env:Path += ";C:\ffmpeg\bin"

Example:
    python generate_segmented_lesson_mp3_language_code.py `
      lesson01.txt `
      --voice-id YOUR_VOICE_ID `
      --model-id eleven_multilingual_v2 `
      --output lesson01.mp3 `
      --max-chars 350 `
      --speech-tempo 0.88 `
      --break-multiplier 1.25

Optional:
    --force-language en
    --force-language zh
    --disable-language-code
    --keep-work
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests


ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

BREAK_RE = re.compile(
    r'<break\s+time=["\']([0-9]+(?:\.[0-9]+)?)s["\']\s*/>',
    flags=re.IGNORECASE,
)


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


def detect_language_code(text: str) -> str | None:
    """
    Auto-detects whether a snippet should be sent to ElevenLabs as English or Chinese.

    Returns:
    - "zh" for Chinese-only snippets
    - "en" for English-only snippets
    - None for mixed or unclear snippets

    This is intentionally conservative:
    - Mixed snippets like "appointment 的意思是：预约。" return None.
    - Best results come from scripts that split English target words/sentences
      and Mandarin instructions into separate snippets using <break> tags or line breaks.
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
    Converts a transcript into ordered segments:
    - {"type": "speech", "text": "..."}
    - {"type": "silence", "seconds": 3.0}

    Exact-text caching note:
    The spoken text is kept exactly except for trimming leading/trailing whitespace
    around speech blocks. Punctuation/capitalization are preserved.
    """
    segments: list[dict[str, Any]] = []
    pos = 0

    for match in BREAK_RE.finditer(script_text):
        before = script_text[pos:match.start()].strip()
        if before:
            segments.append({"type": "speech", "text": before})

        seconds = float(match.group(1))
        if seconds > 0:
            segments.append({"type": "silence", "seconds": seconds})

        pos = match.end()

    after = script_text[pos:].strip()
    if after:
        segments.append({"type": "speech", "text": after})

    return segments


def split_long_speech(text: str, max_chars: int) -> list[str]:
    """
    Splits long speech blocks into smaller chunks.
    This only runs when a speech block exceeds max_chars.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    # Split on sentence endings and line breaks.
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
            # Last resort hard split.
            for i in range(0, len(part), max_chars):
                chunks.append(part[i : i + max_chars])
            current = ""

    if current:
        chunks.append(current)

    return chunks


def normalise_segments(segments: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """
    Splits only overlong speech segments and removes empty segments.
    Does not normalize punctuation/case.
    """
    output: list[dict[str, Any]] = []

    for segment in segments:
        if segment["type"] == "silence":
            seconds = float(segment["seconds"])
            if seconds > 0:
                output.append({"type": "silence", "seconds": seconds})
            continue

        text = segment["text"].strip()
        if not text:
            continue

        for chunk in split_long_speech(text, max_chars=max_chars):
            output.append({"type": "speech", "text": chunk.strip()})

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
    """
    Exact-text cache key.

    Includes language_code because the same text may be generated differently
    with language_code="en" vs no language_code.
    """
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

    params = {
        "output_format": output_format,
    }

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate MP3 from TTS transcript using segmented ElevenLabs requests, automatic language_code, exact cache, local silence, and FFmpeg stitching."
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
        help="Tempo for spoken audio only. 0.90 = 10 percent slower. 1.0 = unchanged.",
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
        "--force-language",
        choices=["en", "zh"],
        default=None,
        help="Force all speech snippets to one language code. Usually leave unset.",
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

    args = parser.parse_args()

    api_key = get_api_key()
    ffmpeg = find_ffmpeg()

    if args.seed == -1:
        args.seed = None

    input_path = args.input_txt
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = args.output or input_path.with_suffix(".mp3")

    args.cache_dir.mkdir(parents=True, exist_ok=True)

    lesson_work_dir = args.work_dir / output_path.stem
    if lesson_work_dir.exists():
        shutil.rmtree(lesson_work_dir, ignore_errors=True)
    lesson_work_dir.mkdir(parents=True, exist_ok=True)

    script_text = input_path.read_text(encoding="utf-8")
    raw_segments = parse_tts_script(script_text)
    segments = normalise_segments(raw_segments, max_chars=args.max_chars)

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Segments: {len(segments)}")
    print(f"Model: {args.model_id}")
    print(f"Voice ID: {args.voice_id}")
    print(f"Speech tempo: {args.speech_tempo}")
    print(f"Break multiplier: {args.break_multiplier}")
    print(f"Minimum break: {args.min_break}")
    print(f"Language code mode: {'disabled' if args.disable_language_code else args.force_language or 'auto'}")
    print(f"FFmpeg: {ffmpeg}")

    final_segment_files: list[Path] = []
    speech_count = 0
    silence_count = 0
    cache_hits = 0
    cache_misses = 0
    lang_counts: dict[str, int] = {"en": 0, "zh": 0, "none": 0}

    for index, segment in enumerate(segments, start=1):
        if segment["type"] == "speech":
            speech_count += 1
            text = segment["text"]

            if args.disable_language_code:
                language_code = None
            elif args.force_language:
                language_code = args.force_language
            else:
                language_code = detect_language_code(text)

            lang_counts[language_code or "none"] += 1

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

            lang_note = language_code or "auto/no-code"

            if raw_speech_path.exists():
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
                tempo=args.speech_tempo,
                bitrate=args.bitrate,
            )

            final_segment_files.append(processed_path)

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

    print(f"Speech segments: {speech_count}")
    print(f"Silence segments: {silence_count}")
    print(f"Cache hits: {cache_hits}")
    print(f"Cache misses: {cache_misses}")
    print(f"Language counts: {lang_counts}")
    print("Concatenating final MP3...")

    concat_mp3_files(
        ffmpeg=ffmpeg,
        input_paths=final_segment_files,
        output_path=output_path,
        bitrate=args.bitrate,
    )

    if not output_path.exists():
        raise RuntimeError(f"Expected output file was not created: {output_path}")

    if not args.keep_work:
        shutil.rmtree(lesson_work_dir, ignore_errors=True)

    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
