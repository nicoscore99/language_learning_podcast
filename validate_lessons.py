#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from generate_lesson_mp3 import (
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
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
MOJIBAKE_RE = re.compile(r"(?:Ã|Â|â€|â€™|â€œ|â€�|ã€|ï¼|æ[\x80-\xbf])")
SPEAKER_LABEL_RE = re.compile(
    r"(?im)^\s*(?:narrator|teacher|student|learner|host|speaker\s*\d*)\s*:"
)
MARKDOWN_RE = re.compile(r"(?m)^\s*(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)")
ENGLISH_SECTION_TITLES = [
    "第一部分，课程介绍。",
    "第二部分，复习。",
    "第三部分，新词介绍。",
    "第四部分，新词练习。",
    "第五部分，情境句子练习。",
    "第六部分，课程总结。",
]


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
            if path.name.lower() not in {"readme_repetition_plan.txt", "validation_summary.txt"} and not path.stem.lower().endswith("_example"):
                files.append(path)
            continue

        if path.is_dir():
            for txt_path in path.rglob("*.txt"):
                if txt_path.name.lower() in {"readme_repetition_plan.txt", "validation_summary.txt"} or txt_path.stem.lower().endswith("_example"):
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
    explicit_auto_segments = sum(
        1
        for segment in raw_segments
        if segment["type"] == "speech" and segment.get("language_code") == "auto"
    )
    unexpected_no_language = max(0, len(no_language_segments) - explicit_auto_segments)
    if unexpected_no_language:
        report.warnings.append(
            f"{unexpected_no_language} speech segment(s) have no language_code after inference"
        )

    if path.name.startswith(("B1_Lesson_", "B2_Lesson_")):
        spoken_texts = [
            segment["text"].strip()
            for segment in raw_segments
            if segment["type"] == "speech"
        ]
        section_positions: list[int] = []
        for title in ENGLISH_SECTION_TITLES:
            if spoken_texts.count(title) != 1:
                report.errors.append(
                    f"required section title must appear exactly once: {title}"
                )
                continue
            section_positions.append(spoken_texts.index(title))
        if (
            len(section_positions) == len(ENGLISH_SECTION_TITLES)
            and section_positions != sorted(section_positions)
        ):
            report.errors.append("required lesson sections are not in the expected order")

        preview_prompt_index = next(
            (
                index
                for index, segment in enumerate(raw_segments)
                if segment["type"] == "speech"
                and segment["text"].strip() == "今天的六个新英语表达是。"
            ),
            None,
        )
        review_title_index = next(
            (
                index
                for index, segment in enumerate(raw_segments)
                if segment["type"] == "speech"
                and segment["text"].strip() == ENGLISH_SECTION_TITLES[1]
            ),
            None,
        )
        if preview_prompt_index is not None and review_title_index is not None:
            preview_segments = raw_segments[preview_prompt_index + 1 : review_title_index]
            preview_english = [
                segment
                for segment in preview_segments
                if segment["type"] == "speech" and segment.get("language_code") == "en"
            ]
            preview_breaks = [
                segment
                for segment in preview_segments
                if segment["type"] == "silence"
            ]
            if len(preview_english) != 6:
                report.errors.append("opening preview must contain six separate English blocks")
            elif any(
                not segment["text"].strip().casefold().startswith(("the ", "to "))
                for segment in preview_english
            ):
                report.errors.append(
                    "opening expressions must identify nouns with 'the' and verbs/adjectives with a 'to' pattern"
                )
            if any(
                segment["text"].strip().casefold().startswith("the to ")
                for segment in preview_english
            ):
                report.errors.append("opening expression contains invalid 'the to' pattern")
            if len(preview_breaks) != 5 or any(
                float(segment["seconds"]) != 1.0 for segment in preview_breaks
            ):
                report.errors.append("opening preview must use five 1.0s breaks")

        for index, segment in enumerate(raw_segments):
            if (
                segment["type"] != "speech"
                or segment.get("language_code") != "zh"
                or not segment["text"].strip().startswith("请说英语：")
            ):
                continue
            following_english = [
                item["text"].strip()
                for item in raw_segments[index + 1 :]
                if item["type"] == "speech" and item.get("language_code") == "en"
            ][:2]
            if len(following_english) != 2 or following_english[0] != following_english[1]:
                report.errors.append(
                    "expression translation prompts must provide the same English answer twice"
                )
                break

        scenario_title_index = next(
            (
                index
                for index, segment in enumerate(raw_segments)
                if segment["type"] == "speech"
                and segment["text"].strip() == ENGLISH_SECTION_TITLES[4]
            ),
            None,
        )
        conclusion_title_index = next(
            (
                index
                for index, segment in enumerate(raw_segments)
                if segment["type"] == "speech"
                and segment["text"].strip() == ENGLISH_SECTION_TITLES[5]
            ),
            None,
        )
        if scenario_title_index is not None and conclusion_title_index is not None:
            scenario_segments = raw_segments[scenario_title_index:conclusion_title_index]
            listen_index = next(
                (
                    index
                    for index, segment in enumerate(scenario_segments)
                    if segment["type"] == "speech"
                    and segment["text"].strip()
                    == "先听每个英语句子，然后在停顿时大声重复。"
                ),
                None,
            )
            translation_index = next(
                (
                    index
                    for index, segment in enumerate(scenario_segments)
                    if segment["type"] == "speech"
                    and segment["text"].strip()
                    == "现在根据中文提示，把这个情境中的句子翻译成英语。"
                ),
                None,
            )
            if translation_index is None:
                report.errors.append("scenario section is missing its Mandarin translation round")
            if listen_index is None:
                report.errors.append("scenario section is missing its listen-and-repeat instruction")
            elif translation_index is not None:
                first_round = scenario_segments[listen_index + 1 : translation_index]
                cursor = 0
                sentence_count = 0
                first_round_ok = True
                while cursor < len(first_round):
                    if sentence_count > 0:
                        prompt = first_round[cursor]
                        if (
                            prompt["type"] != "speech"
                            or prompt.get("language_code") != "zh"
                            or prompt["text"].strip() != "请重复这个英语句子。"
                        ):
                            first_round_ok = False
                            break
                        cursor += 1
                    if cursor + 3 >= len(first_round):
                        first_round_ok = False
                        break
                    first_answer, response_break, repeated_answer, reflection_break = first_round[
                        cursor : cursor + 4
                    ]
                    if not (
                        first_answer["type"] == "speech"
                        and first_answer.get("language_code") == "en"
                        and response_break["type"] == "silence"
                        and repeated_answer["type"] == "speech"
                        and repeated_answer.get("language_code") == "en"
                        and first_answer["text"].strip() == repeated_answer["text"].strip()
                        and reflection_break["type"] == "silence"
                    ):
                        first_round_ok = False
                        break
                    cursor += 4
                    sentence_count += 1
                if not first_round_ok or not 4 <= sentence_count <= 6:
                    report.errors.append(
                        "scenario listen-and-repeat round must use each complete English sentence twice with the repeat prompt before later sentences"
                    )

                translation_round = scenario_segments[translation_index + 1 :]
                cursor = 0
                translated_count = 0
                translation_round_ok = True
                while cursor < len(translation_round):
                    if cursor + 3 >= len(translation_round):
                        translation_round_ok = False
                        break
                    prompt, response_break, answer, reflection_break = translation_round[
                        cursor : cursor + 4
                    ]
                    if not (
                        prompt["type"] == "speech"
                        and prompt.get("language_code") == "zh"
                        and response_break["type"] == "silence"
                        and answer["type"] == "speech"
                        and answer.get("language_code") == "en"
                        and reflection_break["type"] == "silence"
                    ):
                        translation_round_ok = False
                        break
                    cursor += 4
                    translated_count += 1
                if (
                    not translation_round_ok
                    or translated_count != sentence_count
                ):
                    report.errors.append(
                        "scenario translation round must provide one Mandarin prompt and one English answer per scenario sentence"
                    )

    overlong_english_sentences = [
        sentence.strip()
        for segment in raw_segments
        if segment["type"] == "speech" and segment.get("language_code") == "en"
        for sentence in SENTENCE_RE.findall(segment["text"])
        if len(ENGLISH_WORD_RE.findall(sentence)) > 20
    ]
    if overlong_english_sentences:
        report.warnings.append(
            f"{len(overlong_english_sentences)} English sentence(s) exceed 20 words"
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
