#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COURSES_ROOT = ROOT / "curriculum" / "courses"

from validate_lessons import find_lesson_files, validate_file


COURSE_FOLDERS = [
    COURSES_ROOT / "A1_German_TTS_Lesson_Scripts",
    COURSES_ROOT / "B1_English_TTS_Lesson_Scripts",
    COURSES_ROOT / "B2_English_TTS_Lesson_Scripts",
]


def render_summary(folder: Path) -> str:
    reports = [
        validate_file(path, max_break=10.0, max_chars=350)
        for path in find_lesson_files([folder])
    ]

    lines = [
        f"Validation summary for {folder.name}",
        "Standard: LESSON_STYLE.md",
        "Allowed tags: lang=en/de/zh/auto and break",
        "Maximum allowed break: 10.0s",
        "",
    ]

    for report in reports:
        stats = report.stats
        language_counts = ", ".join(
            f"{code}={count}"
            for code, count in sorted(stats["language_counts"].items())
        )
        status = "PASS" if not report.errors and not report.warnings else "REVIEW"

        lines.extend([
            f"filename: {Path(report.path).name}",
            f"status: {status}",
            f"estimated duration: {stats['estimated_duration_minutes']:.1f} minutes",
            f"speech segments: {stats['speech_segments']}",
            f"break tags: {stats['break_tags']}",
            f"max break: {stats['max_break_seconds']:.1f}s",
            f"total break time: {stats['total_break_seconds']:.1f}s",
            f"language counts: {language_counts or 'none'}",
            f"auto tag count: {stats['auto_tag_count']}",
            f"English word count: {stats['english_word_count']}",
            f"CJK character count: {stats['cjk_character_count']}",
            "",
        ])

    total_errors = sum(len(report.errors) for report in reports)
    total_warnings = sum(len(report.warnings) for report in reports)
    lines.extend([
        f"files validated: {len(reports)}",
        f"errors: {total_errors}",
        f"warnings: {total_warnings}",
        f"overall validation: {'PASS' if total_errors == 0 and total_warnings == 0 else 'REVIEW'}",
        "",
    ])

    return "\n".join(lines)


def main() -> None:
    for folder in COURSE_FOLDERS:
        output_path = folder / "validation_summary.txt"
        output_path.write_text(render_summary(folder), encoding="utf-8", newline="\n")
        print(f"Updated: {output_path}")


if __name__ == "__main__":
    main()
