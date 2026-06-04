#!/usr/bin/env python3
"""
Generate segmented lesson MP3s with ElevenLabs TTS + FFmpeg.

Features:
- Parses <break time="Xs" /> tags and creates silence locally with FFmpeg.
- Sends spoken snippets to ElevenLabs individually to reduce long-script voice drift.
- Exact-text caching: identical text, including punctuation/capitalization, reuses the same TTS audio.
- Optional pronunciation dictionary creation from rules via ElevenLabs API.
- Optional pronunciation dictionary use in TTS requests.
- Optional speech tempo slowing with FFmpeg. Silence is not slowed.

Install:
    pip install requests

PowerShell setup:
    $env:ELEVENLABS_API_KEY = "your_api_key"
    $env:Path += ";C:\\ffmpeg\\bin"

Examples:
    python generate_segmented_lesson_mp3_with_dictionary.py create-dictionary `
      --rules-json pronunciation_aliases_b1_course.json `
      --dictionary-name "B1 English Course Pronunciation"

    python generate_segmented_lesson_mp3_with_dictionary.py synthesize `
      lesson01.txt `
      --voice-id YOUR_VOICE_ID `
      --dictionary-locator-json pronunciation_dictionary_locator.json `
      --output lesson01.mp3 `
      --max-chars 350 `
      --speech-tempo 0.88 `
      --break-multiplier 1.25
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
ELEVENLABS_CREATE_DICT_URL = "https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-rules"

BREAK_RE = re.compile(r'<break\s+time=["\']([0-9]+(?:\.[0-9]+)?)s["\']\s*/>', flags=re.IGNORECASE)


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
    raise FileNotFoundError("Could not find ffmpeg. Add it to PATH or place it at C:\\ffmpeg\\bin\\ffmpeg.exe")


def run_command(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Command failed:\n" + " ".join(command) + "\n\nSTDOUT:\n" + result.stdout + "\n\nSTDERR:\n" + result.stderr)


def load_rules_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "rules" in data:
        rules = data["rules"]
    elif isinstance(data, list):
        rules = data
    else:
        raise ValueError("Rules JSON must be either a list of rules or an object with a 'rules' key.")
    if not isinstance(rules, list) or not rules:
        raise ValueError("No pronunciation rules found.")
    for rule in rules:
        if not isinstance(rule, dict) or "string_to_replace" not in rule:
            raise ValueError(f"Invalid rule: {rule!r}")
        if rule.get("type") == "alias":
            if "alias" not in rule:
                raise ValueError(f"Alias rule missing alias: {rule!r}")
        elif rule.get("type") == "phoneme":
            if "phoneme" not in rule or "alphabet" not in rule:
                raise ValueError(f"Phoneme rule missing phoneme/alphabet: {rule!r}")
        else:
            raise ValueError(f"Rule type must be 'alias' or 'phoneme': {rule!r}")
    return rules


def create_pronunciation_dictionary(*, api_key: str, name: str, rules: list[dict[str, Any]], description: str | None = None, timeout: int = 120) -> dict[str, Any]:
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload: dict[str, Any] = {"name": name, "rules": rules}
    if description:
        payload["description"] = description
    response = requests.post(ELEVENLABS_CREATE_DICT_URL, headers=headers, json=payload, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs pronunciation dictionary API error {response.status_code}:\n{response.text}")
    return response.json()


def save_dictionary_locator(response_json: dict[str, Any], output_path: Path) -> None:
    dictionary_id = response_json.get("id")
    version_id = response_json.get("version_id") or response_json.get("latest_version_id")
    if not dictionary_id or not version_id:
        raise RuntimeError(f"Could not find dictionary id/version_id in response:\n{response_json}")
    locator = {"pronunciation_dictionary_id": dictionary_id, "version_id": version_id}
    output_path.write_text(json.dumps(locator, ensure_ascii=False, indent=2), encoding="utf-8")


def load_dictionary_locator_json(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    locators = [data] if isinstance(data, dict) else data
    if not isinstance(locators, list):
        raise ValueError("Dictionary locator JSON must be an object or list of objects.")
    clean = []
    for locator in locators:
        dictionary_id = locator.get("pronunciation_dictionary_id")
        version_id = locator.get("version_id")
        if not dictionary_id or not version_id:
            raise ValueError(f"Invalid dictionary locator: {locator!r}")
        clean.append({"pronunciation_dictionary_id": dictionary_id, "version_id": version_id})
    return clean


def parse_tts_script(script_text: str) -> list[dict[str, Any]]:
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
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    chunks, current = [], ""
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
                for i in range(0, len(part), max_chars):
                    chunks.append(part[i : i + max_chars])
                current = ""
    if current:
        chunks.append(current)
    return chunks


def normalise_segments(segments: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
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


def cache_key_for_speech(*, text: str, voice_id: str, model_id: str, output_format: str, stability: float, similarity_boost: float, style: float, use_speaker_boost: bool, seed: int | None, pronunciation_dictionary_locators: list[dict[str, str]] | None) -> str:
    # EXACT TEXT CACHING: text is included exactly, including punctuation/case.
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
        "pronunciation_dictionary_locators": pronunciation_dictionary_locators or [],
    }
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def call_elevenlabs_tts(*, api_key: str, voice_id: str, text: str, output_path: Path, model_id: str, output_format: str, stability: float, similarity_boost: float, style: float, use_speaker_boost: bool, seed: int | None, pronunciation_dictionary_locators: list[dict[str, str]] | None, timeout: int = 120) -> None:
    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": api_key, "Accept": "audio/mpeg", "Content-Type": "application/json"}
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
    if pronunciation_dictionary_locators:
        payload["pronunciation_dictionary_locators"] = pronunciation_dictionary_locators
    response = requests.post(url, headers=headers, params=params, json=payload, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs API error {response.status_code}:\n{response.text}")
    output_path.write_bytes(response.content)


def make_silence_mp3(*, ffmpeg: str, seconds: float, output_path: Path, sample_rate: int = 44100, bitrate: str = "128k") -> None:
    command = [ffmpeg, "-y", "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono", "-t", f"{seconds:.3f}", "-acodec", "libmp3lame", "-b:a", bitrate, str(output_path)]
    run_command(command)


def slow_down_audio(*, ffmpeg: str, input_path: Path, output_path: Path, tempo: float, bitrate: str = "128k") -> None:
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
    command = [ffmpeg, "-y", "-i", str(input_path), "-filter:a", ",".join(filters), "-vn", "-acodec", "libmp3lame", "-b:a", bitrate, str(output_path)]
    run_command(command)


def concat_mp3_files(*, ffmpeg: str, input_paths: list[Path], output_path: Path, bitrate: str = "128k") -> None:
    list_file = output_path.parent / f"{output_path.stem}_concat_list.txt"
    with list_file.open("w", encoding="utf-8") as f:
        for path in input_paths:
            f.write(f"file '{path.resolve().as_posix()}'\n")
    command = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-acodec", "libmp3lame", "-b:a", bitrate, str(output_path)]
    try:
        run_command(command)
    finally:
        list_file.unlink(missing_ok=True)


def cmd_create_dictionary(args: argparse.Namespace) -> None:
    api_key = get_api_key()
    rules = load_rules_json(args.rules_json)
    print(f"Creating pronunciation dictionary: {args.dictionary_name}")
    print(f"Rules: {len(rules)}")
    response_json = create_pronunciation_dictionary(api_key=api_key, name=args.dictionary_name, rules=rules, description=args.description)
    args.response_json_out.write_text(json.dumps(response_json, ensure_ascii=False, indent=2), encoding="utf-8")
    save_dictionary_locator(response_json, args.locator_json_out)
    print("Created dictionary.")
    print(f"Full response saved to: {args.response_json_out}")
    print(f"Locator saved to: {args.locator_json_out}")


def cmd_synthesize(args: argparse.Namespace) -> None:
    api_key = get_api_key()
    ffmpeg = find_ffmpeg()
    input_path = args.input_txt
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    output_path = args.output or input_path.with_suffix(".mp3")
    dictionary_locators = load_dictionary_locator_json(args.dictionary_locator_json) if args.dictionary_locator_json else None
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    lesson_work_dir = args.work_dir / output_path.stem
    if lesson_work_dir.exists():
        shutil.rmtree(lesson_work_dir, ignore_errors=True)
    lesson_work_dir.mkdir(parents=True, exist_ok=True)
    script_text = input_path.read_text(encoding="utf-8")
    segments = normalise_segments(parse_tts_script(script_text), max_chars=args.max_chars)
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Segments: {len(segments)}")
    print(f"Model: {args.model_id}")
    print(f"Voice ID: {args.voice_id}")
    print(f"Speech tempo: {args.speech_tempo}")
    print(f"FFmpeg: {ffmpeg}")
    if dictionary_locators:
        print(f"Using pronunciation dictionary locator(s): {dictionary_locators}")
    final_segment_files: list[Path] = []
    speech_count = silence_count = cache_hits = cache_misses = 0
    for index, segment in enumerate(segments, start=1):
        if segment["type"] == "speech":
            speech_count += 1
            text = segment["text"]  # exact text, including punctuation/capitalization after block trim
            key = cache_key_for_speech(text=text, voice_id=args.voice_id, model_id=args.model_id, output_format=args.output_format, stability=args.stability, similarity_boost=args.similarity_boost, style=args.style, use_speaker_boost=not args.no_speaker_boost, seed=args.seed, pronunciation_dictionary_locators=dictionary_locators)
            raw_speech_path = args.cache_dir / f"{key}.mp3"
            processed_path = lesson_work_dir / f"{index:05d}_speech.mp3"
            if raw_speech_path.exists():
                cache_hits += 1
                print(f"[{index}/{len(segments)}] speech cache HIT: {len(text)} chars")
            else:
                cache_misses += 1
                print(f"[{index}/{len(segments)}] speech cache MISS; generating: {len(text)} chars")
                call_elevenlabs_tts(api_key=api_key, voice_id=args.voice_id, text=text, output_path=raw_speech_path, model_id=args.model_id, output_format=args.output_format, stability=args.stability, similarity_boost=args.similarity_boost, style=args.style, use_speaker_boost=not args.no_speaker_boost, seed=args.seed, pronunciation_dictionary_locators=dictionary_locators)
                time.sleep(args.sleep)
            slow_down_audio(ffmpeg=ffmpeg, input_path=raw_speech_path, output_path=processed_path, tempo=args.speech_tempo, bitrate=args.bitrate)
            final_segment_files.append(processed_path)
        elif segment["type"] == "silence":
            silence_count += 1
            seconds = max(args.min_break, float(segment["seconds"]) * args.break_multiplier)
            silence_path = lesson_work_dir / f"{index:05d}_silence_{seconds:.2f}s.mp3"
            print(f"[{index}/{len(segments)}] silence: {seconds:.2f}s")
            make_silence_mp3(ffmpeg=ffmpeg, seconds=seconds, output_path=silence_path, bitrate=args.bitrate)
            final_segment_files.append(silence_path)
    print(f"Speech segments: {speech_count}")
    print(f"Silence segments: {silence_count}")
    print(f"Cache hits: {cache_hits}")
    print(f"Cache misses: {cache_misses}")
    print("Concatenating final MP3...")
    concat_mp3_files(ffmpeg=ffmpeg, input_paths=final_segment_files, output_path=output_path, bitrate=args.bitrate)
    if not output_path.exists():
        raise RuntimeError(f"Expected output file was not created: {output_path}")
    if not args.keep_work:
        shutil.rmtree(lesson_work_dir, ignore_errors=True)
    print(f"Done: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ElevenLabs segmented TTS generator with exact-text caching and pronunciation dictionary support.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create-dictionary", help="Create an ElevenLabs pronunciation dictionary from rules JSON.")
    create_parser.add_argument("--rules-json", type=Path, required=True)
    create_parser.add_argument("--dictionary-name", required=True)
    create_parser.add_argument("--description", default="Pronunciation dictionary for B1 English course target vocabulary.")
    create_parser.add_argument("--response-json-out", type=Path, default=Path("pronunciation_dictionary_response.json"))
    create_parser.add_argument("--locator-json-out", type=Path, default=Path("pronunciation_dictionary_locator.json"))
    create_parser.set_defaults(func=cmd_create_dictionary)
    synth_parser = subparsers.add_parser("synthesize", help="Synthesize a lesson transcript into MP3 using segmented TTS + FFmpeg stitching.")
    synth_parser.add_argument("input_txt", type=Path)
    synth_parser.add_argument("--voice-id", required=True)
    synth_parser.add_argument("--output", type=Path, default=None)
    synth_parser.add_argument("--model-id", default="eleven_multilingual_v2")
    synth_parser.add_argument("--output-format", default="mp3_44100_128")
    synth_parser.add_argument("--bitrate", default="128k")
    synth_parser.add_argument("--max-chars", type=int, default=350, help="Maximum characters per ElevenLabs request.")
    synth_parser.add_argument("--stability", type=float, default=0.65)
    synth_parser.add_argument("--similarity-boost", type=float, default=0.80)
    synth_parser.add_argument("--style", type=float, default=0.0)
    synth_parser.add_argument("--no-speaker-boost", action="store_true")
    synth_parser.add_argument("--seed", type=int, default=12345, help="Best-effort deterministic seed. Set to -1 to omit seed.")
    synth_parser.add_argument("--dictionary-locator-json", type=Path, default=None, help="JSON file containing pronunciation_dictionary_id and version_id.")
    synth_parser.add_argument("--speech-tempo", type=float, default=0.90, help="Tempo for spoken audio only. 0.90 = 10 percent slower.")
    synth_parser.add_argument("--min-break", type=float, default=0.0)
    synth_parser.add_argument("--break-multiplier", type=float, default=1.0)
    synth_parser.add_argument("--cache-dir", type=Path, default=Path("tts_cache"))
    synth_parser.add_argument("--work-dir", type=Path, default=Path("tts_work"))
    synth_parser.add_argument("--sleep", type=float, default=0.2)
    synth_parser.add_argument("--keep-work", action="store_true")
    synth_parser.set_defaults(func=cmd_synthesize)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "seed") and args.seed == -1:
        args.seed = None
    args.func(args)


if __name__ == "__main__":
    main()
