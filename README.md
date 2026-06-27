# Language Learning Podcast Pipeline

This repository contains source scripts and lesson transcripts for generating audio language-learning podcasts with ElevenLabs TTS and FFmpeg.

The lesson `.txt` files are the source of truth. Generated audio, TTS cache files, local work directories, and local command/key files are intentionally ignored by Git.

## Project Layout

- `generate_lesson_mp3.py` - canonical TTS generator.
- `generate_subtitles.py` - creates standard SRT and flowing styled ASS subtitles from a completed manifest.
- `render_lesson_video.py` - renders lesson audio and ASS subtitles over an image or looping video.
- `video_style.json` - reusable video dimensions, subtitle frame, typography, colors, and animation settings.
- `standardize_lessons.py` - applies shared tag, formatting, pause, and B1 English-quality rules.
- `rebuild_english_lessons.py` - rebuilds B1 and B2 lessons in the six-section, scenario-based format.
- `validate_lessons.py` - local QA checks for lesson scripts before synthesis.
- `refresh_validation_summaries.py` - refreshes per-course validation reports.
- `LESSON_STYLE.md` - sole authoritative lesson-generation, pedagogy, formatting, caching, and validation specification.
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

Apply the shared lesson standard and refresh reports:

```powershell
python standardize_lessons.py
python rebuild_english_lessons.py
python refresh_validation_summaries.py
```

Recurring Mandarin instructions are identical standalone speech blocks. The generator reuses complete spoken blocks through its exact-text cache; it never assembles sentences from cached word fragments.

## Dry Run

Dry-run a lesson without calling ElevenLabs or FFmpeg. This also writes a sidecar manifest JSON by default:

```powershell
python generate_lesson_mp3.py `
  A1_German_TTS_Lesson_Scripts\A1_Lesson_01_Greetings_and_saying_who_you_are.txt `
  --voice-id YOUR_VOICE_ID `
  --dry-run
```

The default manifest path is the output path with `.manifest.json` as the suffix. Use `--manifest path\to\lesson.manifest.json` to choose a path, or `--no-manifest` to skip manifest output.

## Generate Audio

Generate one lesson:

```powershell
python generate_lesson_mp3.py `
  A1_German_TTS_Lesson_Scripts\A1_Lesson_01_Greetings_and_saying_who_you_are.txt `
  --voice-id YOUR_VOICE_ID `
  --model-id eleven_multilingual_v2 `
  --output A1_German_TTS_Lesson_Scripts\A1_Lesson_01_Greetings_and_saying_who_you_are.mp3 `
  --max-chars 350 `
  --teacher-language en `
  --teacher-speech-tempo 1.0 `
  --target-language de `
  --target-speech-tempo 0.88 `
  --speech-tempo 1.0 `
  --break-multiplier 1.0 `
  --normalize-loudness
```

Teacher and target tempo are applied by matching each speech block's language code. Explicit `<lang>` tags take priority, and `--default-language` classifies otherwise untagged blocks. Use `--speech-tempo` as the fallback for mixed or otherwise unmatched speech. A1 narrator blocks sometimes use `<lang code="auto" />` because they quote German, so its fallback tempo is set to the teacher tempo above. For B1/B2 English lessons, use `--teacher-language zh --target-language en`.

The manifest records the source and generator hashes, exact command, runtime information, all TTS and processing settings, each speech/silence segment, cache keys, rendered breaks, segment timings, and the final MP3 hash. Keep the `.manifest.json` beside its MP3 as the reproducibility record and future subtitle/video timing source.

MP3 files can also contain ID3 metadata, but ID3 tags are not suitable as the primary reproducibility record. They are limited, less convenient for structured data, and can be rewritten by media software. The JSON sidecar is plain text, machine-readable, and records substantially more detail. It never includes the ElevenLabs API key.

Manifests are ignored by Git by default because they are generated artifacts. Remove `*.manifest.json` from `.gitignore` if you want to version them alongside the lesson scripts.

By default, loudness normalization targets `-16 LUFS` integrated loudness, `-1.5 dBTP` true peak, and `11 LRA`. You can adjust those with:

```powershell
--loudness-target-i -16 `
--loudness-target-tp -1.5 `
--loudness-target-lra 11
```

## Generate A Full Folder

The generator processes one lesson at a time. Use a PowerShell loop to generate every production lesson in a folder sequentially with the same settings.

Set the folder, voice, and shared generation settings:

```powershell
$folder = "B2_English_TTS_Lesson_Scripts"
$voiceId = "YOUR_VOICE_ID"

$lessons = Get-ChildItem -Path $folder -Filter "B2_Lesson_*.txt" |
  Where-Object { $_.BaseName -notlike "*_example" } |
  Sort-Object Name
```

Validate and dry-run the folder before spending TTS credits:

```powershell
python validate_lessons.py $folder --strict
if ($LASTEXITCODE -ne 0) {
  throw "Lesson validation failed."
}

foreach ($lesson in $lessons) {
  python generate_lesson_mp3.py `
    $lesson.FullName `
    --voice-id $voiceId `
    --model-id eleven_multilingual_v2 `
    --max-chars 350 `
    --teacher-language zh `
    --teacher-speech-tempo 1.0 `
    --target-language en `
    --target-speech-tempo 0.88 `
    --break-multiplier 1.0 `
    --stability 0.65 `
    --similarity-boost 0.80 `
    --style 0.0 `
    --normalize-loudness `
    --dry-run `
    --no-manifest

  if ($LASTEXITCODE -ne 0) {
    throw "Dry run failed for $($lesson.Name)."
  }
}
```

Generate every lesson:

```powershell
foreach ($lesson in $lessons) {
  python generate_lesson_mp3.py `
    $lesson.FullName `
    --voice-id $voiceId `
    --model-id eleven_multilingual_v2 `
    --max-chars 350 `
    --teacher-language zh `
    --teacher-speech-tempo 1.0 `
    --target-language en `
    --target-speech-tempo 0.88 `
    --break-multiplier 1.0 `
    --stability 0.65 `
    --similarity-boost 0.80 `
    --style 0.0 `
    --normalize-loudness

  if ($LASTEXITCODE -ne 0) {
    throw "Generation failed for $($lesson.Name)."
  }
}
```

Without `--output`, each MP3 and its manifest are written beside the source lesson:

```text
B2_Lesson_01_Opinions_and_Debate.txt
B2_Lesson_01_Opinions_and_Debate.mp3
B2_Lesson_01_Opinions_and_Debate.manifest.json
```

Generation is sequential to make failures and API-rate limits easier to manage. Re-running the loop is safe: identical complete speech blocks with identical TTS settings reuse the exact-text cache. Keep the settings unchanged across a course for consistent voices and maximum cache reuse.

To generate B1 or A1, change `$folder` and the `-Filter` value to `B1_Lesson_*.txt` or `A1_Lesson_*.txt`.

## Generate Subtitles And Video

Subtitle generation requires a completed synthesis manifest because it uses the measured timing of every processed speech and silence segment. A dry-run manifest does not contain these timings.

Generate both standard SRT subtitles and the flowing styled ASS subtitles used by the video renderer:

```powershell
python generate_subtitles.py `
  B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.manifest.json
```

The SRT contains one compatible subtitle cue per speech block. The ASS file displays surrounding speech blocks inside the frame configured in `video_style.json`, keeps the active block highlighted at the center, and moves the text upward before the next block begins.

Render with a static image:

```powershell
python render_lesson_video.py `
  B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.mp3 `
  B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.ass `
  --background-image background.jpg `
  --output B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.mp4
```

Render with a short video that repeats until the lesson ends:

```powershell
python render_lesson_video.py `
  lesson.mp3 `
  lesson.ass `
  --background-video background_loop.mp4 `
  --output lesson.mp4
```

Render a short styling preview before processing the full lesson:

```powershell
python render_lesson_video.py `
  lesson.mp3 `
  lesson.ass `
  --background-image background.jpg `
  --preview-start 60 `
  --preview-duration 20 `
  --output lesson_preview.mp4
```

Adjust `video_style.json` to define the output resolution and frame rate, the allowed subtitle area, active/inactive text styles, visible surrounding lines, line spacing, and transition duration.

## Remotion Waveform Demo

The Remotion demo renders a white-background layout with centered text and a compact animated waveform pill. The waveform is drawn with SVG paths and reacts to the lesson audio.

Install dependencies once:

```powershell
npm install
```

Place a local demo audio file in Remotion's public asset folder:

```powershell
Copy-Item B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.mp3 public\demo-audio.mp3
```

Render the demo:

```powershell
npm run remotion:render:demo
```

The demo props live in `remotion/demo-props.json`. Change `previousText`, `currentText`, and `nextText` for the sentence stack. Change `waveform.colors` for different flag palettes, and adjust width, height, position, opacity, amplitude, sample count, and smoothing there.

To iterate on the waveform ribbon by itself, edit `remotion/ribbon-still-props.json` and render a static PNG:

```powershell
npm run remotion:still:ribbon
```

The PNG is written to `out/waveform-ribbon-still.png`. Change `frame` in the props file to sample a different moment in the audio-driven waveform.

Render a short ribbon-only video with audio:

```powershell
npm run remotion:render:ribbon
```

The MP4 is written to `out/waveform-ribbon-test.mp4`. It uses the same waveform settings from `remotion/ribbon-still-props.json`, centered and scaled inside a `640x320` video.

## Script Reference

### `generate_lesson_mp3.py`

Parses one tagged lesson, generates and caches complete speech blocks with ElevenLabs, renders pauses locally, applies speech tempo and optional loudness normalization, joins the MP3, and writes a reproducibility manifest.

- `input_txt` - required lesson `.txt` path.
- `--voice-id` - required ElevenLabs voice ID.
- `--output` - output MP3 path; defaults beside the input lesson.
- `--model-id`, `--output-format`, `--bitrate` - ElevenLabs model, API audio format, and final MP3 bitrate.
- `--max-chars` - maximum characters sent in one TTS request.
- `--stability`, `--similarity-boost`, `--style`, `--no-speaker-boost`, `--seed` - ElevenLabs voice settings. Use `--seed -1` to omit the seed.
- `--speech-tempo` - fallback tempo for unmatched speech; `1.0` is unchanged and `0.90` is 10 percent slower.
- `--teacher-language`, `--teacher-speech-tempo` - narrator/teacher language code and its tempo.
- `--target-language`, `--target-speech-tempo` - taught language code and its tempo.
- `--min-break`, `--break-multiplier` - minimum pause length and multiplier applied to every `<break>` tag.
- `--normalize-loudness`, `--loudness-target-i`, `--loudness-target-tp`, `--loudness-target-lra` - final FFmpeg loudness normalization and targets.
- `--default-language`, `--disable-language-code` - fallback language for untagged blocks, or prevent language codes from being sent to ElevenLabs.
- `--cache-dir`, `--work-dir`, `--sleep`, `--keep-work` - cache/work locations, API delay, and temporary-file retention.
- `--manifest`, `--no-manifest` - choose the manifest path or disable it.
- `--dry-run` - parse, preview, and optionally write a manifest without calling ElevenLabs or FFmpeg.

### `validate_lessons.py`

Validates lesson files before synthesis. It accepts one or more file or folder `paths`.

- `--max-break`, `--max-chars` - warning thresholds for pauses and speech-block length.
- `--strict` - fail when warnings are present.
- `--json` - print the full machine-readable report.

### `generate_subtitles.py`

Reads a completed lesson manifest and creates standard SRT plus flowing styled ASS subtitles.

- `manifest` - required completed `.manifest.json` path.
- `--config` - style configuration path; defaults to `video_style.json`.
- `--srt-output`, `--ass-output` - choose output paths.
- `--languages` - include only specified exact language codes.
- `--srt-speech-only` - end SRT cues when speech ends instead of holding until the next speech block.
- `--no-srt`, `--no-ass` - disable either output format.

### `render_lesson_video.py`

Uses FFmpeg to burn flowing ASS subtitles over a static image or repeating video and attach the lesson audio.

- `audio`, `subtitles` - required lesson audio and ASS paths.
- `--background-image`, `--background-video` - choose exactly one background source.
- `--output`, `--config` - output MP4 and style configuration paths.
- `--preview-start`, `--preview-duration` - render only a short time range for testing.
- `--video-codec`, `--preset`, `--crf` - video encoder and quality settings.
- `--audio-codec`, `--audio-bitrate` - output audio settings.
- `--dry-run` - print the FFmpeg command without rendering.

### Lesson Maintenance Scripts

These scripts currently take no command-line options:

- `standardize_lessons.py` - applies shared formatting, tag, pause, and quality rules to configured lesson folders.
- `rebuild_english_lessons.py` - rebuilds all B1/B2 lessons in the canonical six-section format.
- `refresh_validation_summaries.py` - refreshes the validation summary in each course folder.
- `naturalize_english_lessons.py` - deprecated older English rewrite script; it is incompatible with the current six-section lesson format.

Use `python SCRIPT_NAME.py --help` for defaults and current CLI help on the generator, validator, subtitle, and video scripts. Do not pass `--help` to the maintenance scripts because they execute immediately.

## Current Pipeline Direction

Near-term improvements:

- Add a dedicated batch-generation CLI with resumable progress reporting.
- Add word-level timing when a reliable alignment source is available.
- Add batch subtitle and video rendering for full course folders.
