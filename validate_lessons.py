#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from generate_segmented_lesson_mp3_langtags import (
    BREAK_RE,
    LANG_RE,
    TAG_RE,
    normalise_segments,
    parse_tts_script,
)


ALLOWED_TAG_RE = re.compile(
    r'<(?:break\s+time=["\'][0-9]+(?:\.[0-9]+)?s["\']\s*/|lang\s+code=["\'](?:auto|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)["\']\s*/)>',
    flags=re.IGNORECASE,
)
ANY_TAG_RE = re.compile(r"<[^>\n]+>")
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
MOJIBAKE_RE = re.compile(r"(?:Ã|Â|â€|â€™|â€œ|â€�|ã€|ï¼|æ[\x80-\xbf])")
SPEAKER_LABEL_RE = re.compile(
    r"(?im)^\s*(?:narrator|teacher|student|learner|host|speaker\s*\d*)\s*:"
)
MARKDOWN_RE = re.compile(r"(?m)^\s*(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)")


@dataclass
class LessonReport:
    path: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def configure_console_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def find_lesson_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []

    for path in paths:
        if path.is_file() and path.suffix.lower() == ".txt":
            if path.name.lower() not in {"readme_repetition_plan.txt", "validation_summary.txt"}:
                files.append(path)
            continue

        if path.is_dir():
            for txt_path in path.rglob("*.txt"):
                if txt_path.name.lower() in {"readme_repetition_plan.txt", "validation_summary.txt"}:
                    continue
                files.append(txt_path)
            continue

        raise FileNotFoundError(f"Path is not a .txt file or directory: {path}")

    return sorted(set(files), key=lambda item: item.as_posix().lower())


def estimate_spoken_seconds(segments: list[dict[str, Any]]) -> float:
    seconds = 0.0

    for segment in segments:
        if segment["type"] == "silence":
            seconds += float(segment["seconds"])
            continue

        text = segment["text"]
        language = segment.get("language_code")
        english_words = len(ENGLISH_WORD_RE.findall(text))
        cjk_chars = len(CJK_RE.findall(text))
        other_chars = len(text) - cjk_chars

        if language == "zh" or cjk_chars > english_words * 2:
            seconds += cjk_chars / 4.0
            seconds += max(0, other_chars) / 18.0
        else:
            seconds += english_words / 2.35
            seconds += cjk_chars / 4.0

    return seconds


def validate_file(path: Path, max_break: float, max_chars: int) -> LessonReport:
    report = LessonReport(path=str(path))
    text = path.read_text(encoding="utf-8")

    unknown_tags = [
        match.group(0)
        for match in ANY_TAG_RE.finditer(text)
        if not ALLOWED_TAG_RE.fullmatch(match.group(0))
    ]
    if unknown_tags:
        preview = ", ".join(sorted(set(unknown_tags))[:5])
        report.errors.append(f"unknown or unsupported tag(s): {preview}")

    break_values = [float(match.group(1)) for match in BREAK_RE.finditer(text)]
    long_breaks = [value for value in break_values if value > max_break]
    if long_breaks:
        report.errors.append(
            f"break duration exceeds {max_break:.1f}s: max {max(long_breaks):.1f}s"
        )

    non_positive_breaks = [value for value in break_values if value <= 0]
    if non_positive_breaks:
        report.errors.append("break duration must be greater than 0")

    if MOJIBAKE_RE.search(text):
        report.warnings.append("possible mojibake/encoding artifacts found")

    if SPEAKER_LABEL_RE.search(text):
        report.warnings.append("speaker-label-like text found")

    if MARKDOWN_RE.search(text):
        report.warnings.append("markdown/list-like formatting found")

    raw_segments = parse_tts_script(text)
    segments = normalise_segments(raw_segments, max_chars=max_chars)

    leaked_tags = [
        segment["text"]
        for segment in segments
        if segment["type"] == "speech" and ANY_TAG_RE.search(segment["text"])
    ]
    if leaked_tags:
        preview = leaked_tags[0].replace("\n", " ")[:100]
        report.errors.append(f"metadata tag leaked into speech text: {preview}")

    speech_segments = [segment for segment in segments if segment["type"] == "speech"]
    silence_segments = [segment for segment in segments if segment["type"] == "silence"]
    no_language_segments = [
        segment for segment in speech_segments if not segment.get("language_code")
    ]
    if no_language_segments:
        report.warnings.append(
            f"{len(no_language_segments)} speech segment(s) have no language_code after inference"
        )

    overlong_speech = [
        segment for segment in speech_segments if len(segment["text"]) > max_chars
    ]
    if overlong_speech:
        report.warnings.append(
            f"{len(overlong_speech)} speech segment(s) exceed max_chars after splitting"
        )

    lang_counts: dict[str, int] = {}
    for segment in speech_segments:
        key = segment.get("language_code") or "none"
        lang_counts[key] = lang_counts.get(key, 0) + 1

    report.stats = {
        "speech_segments": len(speech_segments),
        "silence_segments": len(silence_segments),
        "break_tags": len(break_values),
        "max_break_seconds": max(break_values) if break_values else 0.0,
        "total_break_seconds": sum(break_values),
        "estimated_duration_minutes": estimate_spoken_seconds(segments) / 60.0,
        "english_word_count": len(ENGLISH_WORD_RE.findall(text)),
        "cjk_character_count": len(CJK_RE.findall(text)),
        "lang_tag_count": len(LANG_RE.findall(text)),
        "auto_tag_count": len(
            re.findall(r'<lang\s+code=["\']auto["\']\s*/>', text, flags=re.IGNORECASE)
        ),
        "language_counts": lang_counts,
    }

    return report


def print_text_report(reports: list[LessonReport], strict: bool) -> None:
    total_errors = sum(len(report.errors) for report in reports)
    total_warnings = sum(len(report.warnings) for report in reports)
    failed = [
        report
        for report in reports
        if report.errors or (strict and report.warnings)
    ]

    print(f"Validated files: {len(reports)}")
    print(f"Errors: {total_errors}")
    print(f"Warnings: {total_warnings}")
    print(f"Strict mode: {'on' if strict else 'off'}")

    if reports:
        durations = [report.stats["estimated_duration_minutes"] for report in reports]
        max_break = max(report.stats["max_break_seconds"] for report in reports)
        print(f"Estimated duration range: {min(durations):.1f}-{max(durations):.1f} min")
        print(f"Max break observed: {max_break:.1f}s")

    if failed:
        print("\nFiles needing attention:")
        for report in failed[:30]:
            print(f"- {report.path}")
            for error in report.errors:
                print(f"  ERROR: {error}")
            if strict:
                for warning in report.warnings:
                    print(f"  WARNING: {warning}")
        if len(failed) > 30:
            print(f"... {len(failed) - 30} more")

    warning_only = [
        report for report in reports if report.warnings and not report.errors
    ]
    if warning_only and not strict:
        print("\nWarnings:")
        for report in warning_only[:30]:
            print(f"- {report.path}")
            for warning in report.warnings:
                print(f"  WARNING: {warning}")
        if len(warning_only) > 30:
            print(f"... {len(warning_only) - 30} more")

    print("\nPer-folder summary:")
    folder_stats: dict[str, dict[str, float]] = {}
    for report in reports:
        folder = str(Path(report.path).parent)
        stats = folder_stats.setdefault(
            folder,
            {"files": 0, "minutes": 0.0, "breaks": 0, "errors": 0, "warnings": 0},
        )
        stats["files"] += 1
        stats["minutes"] += report.stats["estimated_duration_minutes"]
        stats["breaks"] += report.stats["break_tags"]
        stats["errors"] += len(report.errors)
        stats["warnings"] += len(report.warnings)

    for folder, stats in sorted(folder_stats.items()):
        average_minutes = stats["minutes"] / stats["files"]
        print(
            f"- {folder}: {int(stats['files'])} files, "
            f"avg {average_minutes:.1f} min, "
            f"{int(stats['breaks'])} breaks, "
            f"{int(stats['errors'])} errors, "
            f"{int(stats['warnings'])} warnings"
        )


def main() -> int:
    configure_console_output()

    parser = argparse.ArgumentParser(
        description="Validate tagged TTS lesson scripts before synthesis."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Lesson .txt file(s) or directories containing lesson .txt files.",
    )
    parser.add_argument("--max-break", type=float, default=10.0)
    parser.add_argument("--max-chars", type=int, default=350)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a failing exit code when warnings are present.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full machine-readable report JSON.",
    )

    args = parser.parse_args()
    files = find_lesson_files(args.paths)
    reports = [
        validate_file(path, max_break=args.max_break, max_chars=args.max_chars)
        for path in files
    ]

    if args.json:
        print(json.dumps([report.__dict__ for report in reports], ensure_ascii=False, indent=2))
    else:
        print_text_report(reports, strict=args.strict)

    has_errors = any(report.errors for report in reports)
    has_strict_warnings = args.strict and any(report.warnings for report in reports)
    return 1 if has_errors or has_strict_warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())

