# Language Learning Podcast Pipeline

This repository contains source scripts and lesson transcripts for generating audio language-learning podcasts with ElevenLabs TTS and FFmpeg.

The lesson `.txt` files are the source of truth. Generated audio, TTS cache files, local work directories, and local command/key files are intentionally ignored by Git.

## Project Layout

- `generate_segmented_lesson_mp3_langtags.py` - canonical TTS generator.
- `validate_lessons.py` - local QA checks for lesson scripts before synthesis.
- `A1_German_TTS_Lesson_Scripts/` - A1 German lesson scripts.
- `B1_English_TTS_Lesson_Scripts/` - B1 English lesson scripts for Mandarin-speaking learners.
- `B2_English_TTS_Lesson_Scripts/` - B2 English lesson scripts for Mandarin-speaking learners.
- `tts_cache/` - generated speech snippet cache, ignored by Git.
- `tts_work/` - temporary stitching output, ignored by Git.

## Requirements

- Python 3.10+
- FFmpeg available on `PATH`
- ElevenLabs API key in `ELEVENLABS_API_KEY`
- Python package:

```powershell
pip install requests
```

On Windows PowerShell:

```powershell
$env:ELEVENLABS_API_KEY = "your_key_here"
$env:Path += ";C:\ffmpeg\bin"
```

For persistent local configuration, copy `.env.example` to `.env` and keep real secrets out of Git.

## Lesson Format

Lesson files may contain only spoken text plus these metadata tags:

```xml
<lang code="en" />
<lang code="zh" />
<lang code="de" />
<lang code="auto" />
<break time="3.0s" />
```

Language tags are removed before sending text to TTS. `<lang code="auto" />` asks the generator to infer the language for that block. Break tags are rendered locally as silence with FFmpeg.

## Validate Lessons

Run the validator before spending TTS credits:

```powershell
python validate_lessons.py A1_German_TTS_Lesson_Scripts B1_English_TTS_Lesson_Scripts B2_English_TTS_Lesson_Scripts
```

The validator checks for unknown tags, break durations, leaked metadata tags, speaker labels, markdown-like formatting, mojibake patterns, language-tag coverage, and rough duration stats.

Use strict mode to fail on warnings too:

```powershell
python validate_lessons.py A1_German_TTS_Lesson_Scripts --strict
```

## Dry Run

Dry-run a lesson without calling ElevenLabs or FFmpeg. This also writes a sidecar manifest JSON by default:

```powershell
python generate_segmented_lesson_mp3_langtags.py `
  A1_German_TTS_Lesson_Scripts\A1_Lesson_01_Greetings_and_saying_who_you_are.txt `
  --voice-id YOUR_VOICE_ID `
  --dry-run
```

The default manifest path is the output path with `.manifest.json` as the suffix. Use `--manifest path\to\lesson.manifest.json` to choose a path, or `--no-manifest` to skip manifest output.

## Generate Audio

Generate one lesson:

```powershell
python generate_segmented_lesson_mp3_langtags.py `
  A1_German_TTS_Lesson_Scripts\A1_Lesson_01_Greetings_and_saying_who_you_are.txt `
  --voice-id YOUR_VOICE_ID `
  --model-id eleven_multilingual_v2 `
  --output A1_German_TTS_Lesson_Scripts\A1_Lesson_01_Greetings_and_saying_who_you_are.mp3 `
  --max-chars 350 `
  --speech-tempo 0.90 `
  --break-multiplier 1.0 `
  --normalize-loudness
```

The manifest records each speech/silence segment, inferred language code, text, cache key, requested break duration, rendered break duration, synthesis settings, and post-synthesis segment timings. This is the planned source for subtitles, video timing, and reproducible rebuilds.

By default, loudness normalization targets `-16 LUFS` integrated loudness, `-1.5 dBTP` true peak, and `11 LRA`. You can adjust those with:

```powershell
--loudness-target-i -16 `
--loudness-target-tp -1.5 `
--loudness-target-lra 11
```

## Current Pipeline Direction

Near-term improvements:

- Add batch synthesis for full folders.
- Generate subtitles from the manifest.
- Generate simple video assets from audio plus subtitles.
