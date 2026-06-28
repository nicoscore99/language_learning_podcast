#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
COURSES_ROOT = ROOT / "curriculum" / "courses"
sys.path.insert(0, str(ROOT / "audio"))

from generate_lesson_mp3 import parse_tts_script


COURSES = {
    COURSES_ROOT / "A1_German_TTS_Lesson_Scripts": {"teacher": {"en", "auto"}, "target": "de"},
    COURSES_ROOT / "B1_English_TTS_Lesson_Scripts": {"teacher": {"zh"}, "target": "en"},
    COURSES_ROOT / "B2_English_TTS_Lesson_Scripts": {"teacher": {"zh"}, "target": "en"},
}

BAD_B1_PATTERNS = [
    re.compile(r"I need more information before I can deal with (.+)\."),
    re.compile(r"This is related to (.+), so I would like to confirm it\."),
    re.compile(r"If (.+) is part of the problem, I will check it carefully\."),
    re.compile(r"We can handle (.+) in a simple way\."),
    re.compile(r"Because (.+) is important, I will prepare early\."),
    re.compile(r"Finally, I will record the information about (.+)\."),
]

EXCLUDED_EXAMPLE_PHRASES = (
    "today's six",
    "new english expressions",
    "the main problem is connected",
    "i can talk about",
    "i can put the old word",
    "what information do you need",
)

WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)?")


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def normalize_a1_auto_tags(segments: list[dict[str, Any]]) -> None:
    german_phrases = {
        segment["text"].strip().rstrip(".").casefold()
        for segment in segments
        if segment["type"] == "speech" and segment.get("language_code") == "de"
    }

    for segment in segments:
        if segment["type"] != "speech" or segment.get("language_code") != "auto":
            continue

        text = segment["text"].casefold()
        is_mixed = any(
            phrase and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text)
            for phrase in german_phrases
        )
        if not is_mixed:
            segment["language_code"] = "en"


def standardize_target_punctuation(
    segments: list[dict[str, Any]],
    *,
    target_language: str,
) -> None:
    introduced_targets: list[str] = []

    for index, segment in enumerate(segments):
        if segment["type"] != "speech" or segment.get("language_code") != target_language:
            continue

        previous = find_previous_speech(segments, index)
        if (
            previous
            and previous.get("language_code") == "zh"
            and re.fullmatch(r"第\d+个词", previous["text"].strip())
        ):
            introduced_targets.append(segment["text"].strip().rstrip("."))

        text = segment["text"].strip()
        if (
            count_words(text) <= 3
            and re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’ -]*", text)
            and not re.fullmatch(r"[ABC][12]", text)
        ):
            segment["text"] = text + "."

    if not introduced_targets:
        return

    for index, segment in enumerate(segments):
        if segment["type"] != "speech" or segment.get("language_code") != target_language:
            continue
        previous = find_previous_speech(segments, index)
        if (
            previous
            and previous.get("language_code") == "zh"
            and "六个新英语表达" in previous["text"]
        ):
            segment["text"] = ", ".join(introduced_targets[:6]) + "."
            return


def find_previous_speech(segments: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    for item in reversed(segments[:index]):
        if item["type"] == "speech":
            return item
    return None


def collect_b1_example_map(segments: list[dict[str, Any]]) -> dict[str, str]:
    examples: dict[str, str] = {}

    for index, segment in enumerate(segments):
        if segment["type"] != "speech" or segment.get("language_code") != "zh":
            continue
        if segment["text"].strip() != "例句。":
            continue

        example = next(
            (
                item["text"].strip()
                for item in segments[index + 1 :]
                if item["type"] == "speech" and item.get("language_code") == "en"
            ),
            None,
        )
        target = next(
            (
                item["text"].strip().rstrip(".")
                for item in reversed(segments[:index])
                if item["type"] == "speech"
                and item.get("language_code") == "en"
                and count_words(item["text"]) <= 3
            ),
            None,
        )
        if target and example:
            examples[target.casefold()] = example

    return examples


def find_example_for_word(examples: dict[str, str], word: str) -> str:
    example = examples.get(word.casefold())
    if not example:
        raise ValueError(f"No natural example found for B1 target expression: {word}")
    return example


def find_combined_example(segments: list[dict[str, Any]], words: list[str]) -> str | None:
    patterns = [
        re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", flags=re.IGNORECASE)
        for word in words
    ]

    for segment in segments:
        if segment["type"] != "speech" or segment.get("language_code") != "en":
            continue

        text = segment["text"].strip()
        lowered = text.casefold()
        if count_words(text) < 4 or text.count(",") >= 3:
            continue
        if any(phrase in lowered for phrase in EXCLUDED_EXAMPLE_PHRASES):
            continue
        if all(pattern.search(text) for pattern in patterns):
            return text

    return None


def improve_b1_english(
    segments: list[dict[str, Any]],
    global_examples: dict[str, str],
) -> None:
    examples = collect_b1_example_map(segments)

    for index, segment in enumerate(segments):
        if segment["type"] != "speech" or segment.get("language_code") != "en":
            continue

        text = segment["text"].strip()
        prompt = find_previous_speech(segments, index)

        if prompt and prompt.get("language_code") == "zh":
            prompt_match = re.fullmatch(
                r"请用 (.+) 说一个自然、实用的英文句子。",
                prompt["text"].strip(),
            )
            if prompt_match:
                segment["text"] = find_example_for_word(examples, prompt_match.group(1).strip())
                text = segment["text"].strip()

        for pattern in BAD_B1_PATTERNS:
            match = pattern.fullmatch(text)
            if not match:
                continue

            word = match.group(1).strip()
            segment["text"] = find_example_for_word(examples, word)
            prompt = find_previous_speech(segments, index)
            if prompt and prompt.get("language_code") == "zh":
                prompt["text"] = f"请用 {word} 说一个自然、实用的英文句子。"
            break

        text = segment["text"].strip()
        match = re.fullmatch(
            r"I can put the old word (.+) and the new word (.+) into one real situation\.",
            text,
        )
        if match:
            old_word = match.group(1).strip()
            new_word = match.group(2).strip()
            old_example = find_example_for_word(global_examples, old_word)
            new_example = find_example_for_word(global_examples, new_word)
            segment["text"] = f"{old_example} {new_example}"
            if prompt and prompt.get("language_code") == "zh":
                prompt["text"] = (
                    f"请分别用旧词 {old_word} 和新词 {new_word} "
                    "说两个自然、实用的英文句子。"
                )
            continue

        match = re.fullmatch(
            r'I can use both "(.+)" and "(.+)" when I describe a real situation\.',
            text,
        )
        if match:
            old_word = match.group(1).strip()
            new_word = match.group(2).strip()
            old_example = find_example_for_word(global_examples, old_word)
            new_example = find_example_for_word(global_examples, new_word)
            segment["text"] = f"{old_example} {new_example}"
            if prompt and prompt.get("language_code") == "zh":
                prompt["text"] = (
                    f"请分别用旧词 {old_word} 和新词 {new_word} "
                    "说两个自然、实用的英文句子。"
                )
            continue

        match = re.fullmatch(r"I can use (.+) and (.+) in a real situation\.", text)
        if match:
            old_word = match.group(1).strip()
            new_word = match.group(2).strip()
            old_example = find_example_for_word(global_examples, old_word)
            new_example = find_example_for_word(global_examples, new_word)
            segment["text"] = f"{old_example} {new_example}"
            if prompt and prompt.get("language_code") == "zh":
                prompt["text"] = (
                    f"现在把旧词和新词结合。请分别用 {old_word} 和 {new_word} "
                    "说两个自然、实用的英文句子。"
                )
            continue

        match = re.fullmatch(r"The main problem is connected with (.+) and (.+)\.", text)
        if match:
            segment["text"] = (
                f'The main issue is how to use "{match.group(1)}" and '
                f'"{match.group(2)}" correctly.'
            )
            continue

        match = re.fullmatch(r'The main issue involves both "(.+)" and "(.+)"\.', text)
        if match:
            segment["text"] = (
                f'The main issue is how to use "{match.group(1)}" and '
                f'"{match.group(2)}" correctly.'
            )
            continue

        match = re.fullmatch(r"I need information about (.+), (.+), and (.+)\.", text)
        if match:
            segment["text"] = (
                f'I need to understand how to use "{match.group(1)}", '
                f'"{match.group(2)}", and "{match.group(3)}".'
            )
            continue

        match = re.fullmatch(r"I can talk about (.+) and (.+) in a clear way\.", text)
        if match:
            first_word = match.group(1).strip()
            second_word = match.group(2).strip()
            combined = find_combined_example(segments, [first_word, second_word])
            segment["text"] = combined or (
                f"{find_example_for_word(global_examples, first_word)} "
                f"{find_example_for_word(global_examples, second_word)}"
            )
            continue

        match = re.fullmatch(r'I can use "(.+)" and "(.+)" correctly in a sentence\.', text)
        if match:
            first_word = match.group(1).strip()
            second_word = match.group(2).strip()
            combined = find_combined_example(segments, [first_word, second_word])
            segment["text"] = combined or (
                f"{find_example_for_word(global_examples, first_word)} "
                f"{find_example_for_word(global_examples, second_word)}"
            )
            continue

        if text == "Next, I would check the information and take one clear step.":
            segment["text"] = "Next, I would check the details and decide what to do."
            continue

        if re.fullmatch(
            r"A good final step is to confirm everything and write down the details about .+\.",
            text,
        ):
            segment["text"] = "A good final step is to confirm the details and write them down."
            continue

        if re.fullmatch(
            r"It is important because it helps me manage .+ in daily life\.",
            text,
        ):
            segment["text"] = (
                "It is important because it helps me handle everyday situations more confidently."
            )


def response_pause(answer: str) -> float:
    words = count_words(answer)
    if words <= 1:
        return 3.5
    if words <= 5:
        return 4.5
    if words <= 10:
        return 5.5
    if words <= 16:
        return 6.5
    if words <= 25:
        return 7.5
    return 9.0


def reflection_pause(model: str) -> float:
    words = count_words(model)
    if words <= 1:
        return 2.0
    if words <= 8:
        return 2.5
    if words <= 16:
        return 3.0
    return 4.0


def standardize_pauses(
    segments: list[dict[str, Any]],
    *,
    teacher_languages: set[str],
    target_language: str,
) -> None:
    for index, segment in enumerate(segments):
        if segment["type"] != "silence":
            continue

        previous = segments[index - 1] if index > 0 else None
        following = segments[index + 1] if index + 1 < len(segments) else None

        if not previous or previous["type"] != "speech":
            continue

        previous_language = previous.get("language_code")

        if (
            following
            and following["type"] == "speech"
            and previous_language in teacher_languages
            and following.get("language_code") == target_language
        ):
            segment["seconds"] = response_pause(following["text"])
        elif (
            following
            and following["type"] == "speech"
            and previous_language == target_language
            and following.get("language_code") == target_language
            and previous["text"].rstrip().endswith("?")
        ):
            segment["seconds"] = response_pause(following["text"])
        elif previous_language == target_language:
            segment["seconds"] = reflection_pause(previous["text"])


def render_segments(segments: list[dict[str, Any]]) -> str:
    blocks: list[str] = []

    for segment in segments:
        if segment["type"] == "silence":
            blocks.append(f'<break time="{float(segment["seconds"]):.1f}s" />')
            continue

        language_code = segment.get("language_code")
        if not language_code:
            raise ValueError(f"Speech block has no language tag: {segment['text'][:80]}")
        blocks.append(f'<lang code="{language_code}" />\n{segment["text"].strip()}')

    return "\n\n".join(blocks) + "\n"


def standardize_file(
    path: Path,
    course: dict[str, Any],
    global_b1_examples: dict[str, str],
) -> bool:
    original = path.read_text(encoding="utf-8")
    segments = parse_tts_script(original)

    if path.parent.name == "A1_German_TTS_Lesson_Scripts":
        normalize_a1_auto_tags(segments)
    elif path.parent.name == "B1_English_TTS_Lesson_Scripts":
        improve_b1_english(segments, global_b1_examples)

    standardize_target_punctuation(segments, target_language=course["target"])
    standardize_pauses(
        segments,
        teacher_languages=course["teacher"],
        target_language=course["target"],
    )

    standardized = render_segments(segments)
    if standardized == original.replace("\r\n", "\n"):
        return False

    path.write_text(standardized, encoding="utf-8", newline="\n")
    return True


def main() -> None:
    changed: list[Path] = []
    global_b1_examples: dict[str, str] = {}

    for path in sorted((COURSES_ROOT / "B1_English_TTS_Lesson_Scripts").glob("*Lesson*.txt")):
        if path.stem.lower().endswith("_example"):
            continue
        for word, example in collect_b1_example_map(
            parse_tts_script(path.read_text(encoding="utf-8"))
        ).items():
            global_b1_examples.setdefault(word, example)

    for folder, course in COURSES.items():
        for path in sorted(folder.glob("*Lesson*.txt")):
            if path.stem.lower().endswith("_example"):
                continue
            if standardize_file(path, course, global_b1_examples):
                changed.append(path)

    print(f"Standardized lesson files: {len(changed)}")
    for path in changed:
        print(path)


if __name__ == "__main__":
    main()
