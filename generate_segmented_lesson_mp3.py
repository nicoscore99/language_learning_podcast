import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests


ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


BREAK_RE = re.compile(
    r'<break\s+time=["\']([0-9]+(?:\.[0-9]+)?)s["\']\s*/>',
    flags=re.IGNORECASE,
)


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


def parse_tts_script(script_text: str) -> list[dict]:
    """
    Converts a TTS script into ordered segments:
    - {"type": "speech", "text": "..."}
    - {"type": "silence", "seconds": 3.0}

    Text between <break time="Xs" /> tags becomes speech.
    Break tags become local silence.
    """
    segments = []
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

    # Merge neighbouring speech segments only when there was no break between them.
    # In this parser, breaks are explicit, so we keep order as-is.
    return segments


def split_long_speech(text: str, max_chars: int) -> list[str]:
    """
    Splits long speech blocks into smaller chunks.
    Keeps sentences together when possible.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    chunks = []
    current = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        candidate = (current + "\n" + part).strip() if current else part

        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)

            if len(part) <= max_chars:
                current = part
            else:
                # Last resort: hard split very long text.
                for i in range(0, len(part), max_chars):
                    chunks.append(part[i : i + max_chars])
                current = ""

    if current:
        chunks.append(current)

    return chunks


def normalise_segments(segments: list[dict], max_chars: int) -> list[dict]:
    """
    Splits long speech segments and removes empty segments.
    """
    output = []

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
    }
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


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

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
        },
    }

    response = requests.post(
        url,
        headers=headers,
        params=params,
        json=payload,
        timeout=timeout,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error {response.status_code}:\n{response.text}"
        )

    output_path.write_bytes(response.content)


def make_silence_mp3(
    *,
    ffmpeg: str,
    seconds: float,
    output_path: Path,
    sample_rate: int = 44100,
    bitrate: str = "128k",
) -> None:
    """
    Creates an MP3 file containing silence.
    """
    command = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r={sample_rate}:cl=mono",
        "-t",
        f"{seconds:.3f}",
        "-q:a",
        "9",
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
    """
    Slows down or speeds up audio while preserving pitch.
    tempo < 1.0 = slower.
    tempo > 1.0 = faster.

    Example:
    tempo=0.90 means 10% slower.
    tempo=0.85 means 15% slower.
    """
    if tempo <= 0:
        raise ValueError("Tempo must be greater than 0.")

    if abs(tempo - 1.0) < 0.001:
        shutil.copyfile(input_path, output_path)
        return

    # FFmpeg atempo is most reliable between 0.5 and 2.0 per filter.
    # For normal use, 0.80–1.00 is fine.
    filters = []
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
) -> None:
    """
    Concatenates MP3 files in order.
    Re-encodes for robustness, which avoids many Windows/MP3 edge cases.
    """
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
        "128k",
        str(output_path),
    ]

    try:
        run_command(command)
    finally:
        list_file.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an MP3 from a TTS script by synthesizing snippets separately, adding local silences, slowing speech, and stitching with FFmpeg."
    )

    parser.add_argument("input_txt", type=Path)
    parser.add_argument("--voice-id", required=True)
    parser.add_argument("--output", type=Path, default=None)

    parser.add_argument("--model-id", default="eleven_multilingual_v2")
    parser.add_argument("--output-format", default="mp3_44100_128")

    parser.add_argument(
        "--max-chars",
        type=int,
        default=500,
        help="Maximum characters per ElevenLabs request. Smaller values reduce long-script voice drift.",
    )

    parser.add_argument("--stability", type=float, default=0.65)
    parser.add_argument("--similarity-boost", type=float, default=0.80)
    parser.add_argument("--style", type=float, default=0.0)
    parser.add_argument("--no-speaker-boost", action="store_true")

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

    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="Keep temporary processed segment files.",
    )

    args = parser.parse_args()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing ELEVENLABS_API_KEY environment variable.")

    ffmpeg = find_ffmpeg()

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
    print(f"Speech tempo: {args.speech_tempo}")
    print(f"FFmpeg: {ffmpeg}")

    final_segment_files = []

    speech_count = 0
    silence_count = 0

    for index, segment in enumerate(segments, start=1):
        if segment["type"] == "speech":
            speech_count += 1
            text = segment["text"]

            key = cache_key_for_speech(
                text=text,
                voice_id=args.voice_id,
                model_id=args.model_id,
                output_format=args.output_format,
                stability=args.stability,
                similarity_boost=args.similarity_boost,
                style=args.style,
                use_speaker_boost=not args.no_speaker_boost,
            )

            raw_speech_path = args.cache_dir / f"{key}.mp3"
            processed_path = lesson_work_dir / f"{index:05d}_speech.mp3"

            if raw_speech_path.exists():
                print(f"[{index}/{len(segments)}] speech cached: {len(text)} chars")
            else:
                print(f"[{index}/{len(segments)}] generating speech: {len(text)} chars")
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
                )
                time.sleep(args.sleep)

            slow_down_audio(
                ffmpeg=ffmpeg,
                input_path=raw_speech_path,
                output_path=processed_path,
                tempo=args.speech_tempo,
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
            )

            final_segment_files.append(silence_path)

    print(f"Speech segments: {speech_count}")
    print(f"Silence segments: {silence_count}")
    print("Concatenating final MP3...")

    concat_mp3_files(
        ffmpeg=ffmpeg,
        input_paths=final_segment_files,
        output_path=output_path,
    )

    if not output_path.exists():
        raise RuntimeError(f"Expected output file was not created: {output_path}")

    if not args.keep_work:
        shutil.rmtree(lesson_work_dir, ignore_errors=True)

    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()