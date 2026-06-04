import argparse
import os
import re
import time
from pathlib import Path

import requests
from pydub import AudioSegment


ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def read_text_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise ValueError(f"Input file is empty: {path}")
    return text


def split_transcript(text: str, max_chars: int = 9000) -> list[str]:
    """
    Splits a transcript into chunks below max_chars.

    The splitter tries to preserve natural boundaries:
    1. double newlines
    2. single newlines
    3. sentence punctuation

    It keeps <break time="3.0s" /> tags as text, so ElevenLabs can interpret them.
    """
    if len(text) <= max_chars:
        return [text]

    # First split by paragraph-ish blocks.
    blocks = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    def flush_current():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
            current = ""

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        candidate = (current + "\n\n" + block).strip() if current else block

        if len(candidate) <= max_chars:
            current = candidate
            continue

        flush_current()

        # If a single block is too large, split by lines.
        if len(block) > max_chars:
            lines = block.splitlines()
            line_current = ""

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line_candidate = (
                    line_current + "\n" + line
                ).strip() if line_current else line

                if len(line_candidate) <= max_chars:
                    line_current = line_candidate
                else:
                    if line_current:
                        chunks.append(line_current.strip())
                        line_current = ""

                    if len(line) > max_chars:
                        # Last resort: split by sentence punctuation.
                        sentences = re.split(r"(?<=[.!?。！？])\s+", line)
                        sentence_current = ""

                        for sentence in sentences:
                            sentence = sentence.strip()
                            if not sentence:
                                continue

                            sentence_candidate = (
                                sentence_current + " " + sentence
                            ).strip() if sentence_current else sentence

                            if len(sentence_candidate) <= max_chars:
                                sentence_current = sentence_candidate
                            else:
                                if sentence_current:
                                    chunks.append(sentence_current.strip())
                                sentence_current = sentence

                        if sentence_current:
                            chunks.append(sentence_current.strip())
                    else:
                        line_current = line

            if line_current:
                chunks.append(line_current.strip())
        else:
            current = block

    flush_current()
    return chunks


def synthesize_chunk(
    *,
    api_key: str,
    voice_id: str,
    text: str,
    output_path: Path,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
    stability: float = 0.65,
    similarity_boost: float = 0.80,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    timeout: int = 120,
) -> None:
    """
    Sends one text chunk to ElevenLabs and writes the returned MP3 bytes.
    """
    url = ELEVENLABS_API_URL.format(voice_id=voice_id)

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
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

    params = {
        "output_format": output_format,
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


def combine_mp3_files(chunk_paths: list[Path], final_output_path: Path) -> None:
    """
    Combines MP3 chunk files into one MP3.
    Requires ffmpeg to be installed.
    """
    if not chunk_paths:
        raise ValueError("No MP3 chunks to combine.")

    combined = AudioSegment.empty()

    for chunk_path in chunk_paths:
        audio = AudioSegment.from_mp3(chunk_path)
        combined += audio

    combined.export(final_output_path, format="mp3")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an MP3 from a TTS transcript using ElevenLabs."
    )

    parser.add_argument(
        "input_txt",
        type=Path,
        help="Path to the transcript .txt file.",
    )

    parser.add_argument(
        "--voice-id",
        required=True,
        help="ElevenLabs voice ID.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output MP3 path. Defaults to same name as input .txt.",
    )

    parser.add_argument(
        "--model-id",
        default="eleven_multilingual_v2",
        help="ElevenLabs model ID. Recommended: eleven_multilingual_v2.",
    )

    parser.add_argument(
        "--output-format",
        default="mp3_44100_128",
        help="ElevenLabs output format, e.g. mp3_44100_128.",
    )

    parser.add_argument(
        "--max-chars",
        type=int,
        default=5000,
        help="Max characters per API request. Keep under the model limit.",
    )

    parser.add_argument(
        "--stability",
        type=float,
        default=0.65,
        help="Voice stability, usually 0.0 to 1.0.",
    )

    parser.add_argument(
        "--similarity-boost",
        type=float,
        default=0.80,
        help="Similarity boost, usually 0.0 to 1.0.",
    )

    parser.add_argument(
        "--style",
        type=float,
        default=0.0,
        help="Style exaggeration. Keep low for educational audio.",
    )

    parser.add_argument(
        "--no-speaker-boost",
        action="store_true",
        help="Disable speaker boost.",
    )

    parser.add_argument(
        "--keep-chunks",
        action="store_true",
        help="Keep temporary MP3 chunk files.",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to wait between API requests.",
    )

    args = parser.parse_args()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Missing ELEVENLABS_API_KEY environment variable."
        )

    input_path = args.input_txt
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = args.output or input_path.with_suffix(".mp3")
    temp_dir = output_path.parent / f"{output_path.stem}_chunks"
    temp_dir.mkdir(parents=True, exist_ok=True)

    transcript = read_text_file(input_path)
    chunks = split_transcript(transcript, max_chars=args.max_chars)

    print(f"Input file: {input_path}")
    print(f"Output MP3: {output_path}")
    print(f"Model: {args.model_id}")
    print(f"Voice ID: {args.voice_id}")
    print(f"Chunks: {len(chunks)}")

    chunk_paths = []

    for index, chunk in enumerate(chunks, start=1):
        chunk_path = temp_dir / f"{output_path.stem}_part_{index:03d}.mp3"
        print(
            f"Generating chunk {index}/{len(chunks)} "
            f"({len(chunk)} characters)..."
        )

        synthesize_chunk(
            api_key=api_key,
            voice_id=args.voice_id,
            text=chunk,
            output_path=chunk_path,
            model_id=args.model_id,
            output_format=args.output_format,
            stability=args.stability,
            similarity_boost=args.similarity_boost,
            style=args.style,
            use_speaker_boost=not args.no_speaker_boost,
        )

        chunk_paths.append(chunk_path)

        if index < len(chunks):
            time.sleep(args.sleep)

    print("Combining MP3 chunks...")
    combine_mp3_files(chunk_paths, output_path)

    if not args.keep_chunks:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()