# Language Learning Podcast Pipeline

This project generates language-learning podcast episodes from tagged lesson scripts. The pipeline is split into three parts:

- `curriculum/` - lesson source files, curriculum spreadsheets, style rules, and lesson QA tools.
- `audio/` - ElevenLabs/FFmpeg audio generation and reproducibility manifests.
- `video/` - subtitle generation, FFmpeg video rendering, and Remotion waveform videos.

Generated media, cache files, work folders, and local secrets are ignored by Git.

## Layout

- `curriculum/LESSON_STYLE.md` - canonical lesson style, pedagogy, tagging, caching, and validation rules.
- `curriculum/courses/A1_German_TTS_Lesson_Scripts/` - A1 German lessons.
- `curriculum/courses/B1_English_TTS_Lesson_Scripts/` - B1 English lessons for Mandarin-speaking learners.
- `curriculum/courses/B2_English_TTS_Lesson_Scripts/` - B2 English lessons for Mandarin-speaking learners.
- `curriculum/tools/` - validation, standardization, and lesson rebuild scripts.
- `audio/generate_lesson_mp3.py` - TTS generation, speech cache reuse, MP3 stitching, and manifest creation.
- `video/ffmpeg/generate_subtitles.py` - SRT and flowing ASS subtitle generation from completed manifests.
- `video/ffmpeg/render_lesson_video.py` - FFmpeg renderer for image/video backgrounds plus ASS subtitles.
- `video/ffmpeg/video_style.json` - subtitle/video style config for the FFmpeg renderer.
- `video/manifest_to_remotion_props.py` - converts a completed audio manifest into Remotion subtitle props.
- `video/remotion/` - React/TypeScript Remotion compositions and waveform ribbon settings.
- `public/` - local Remotion assets such as `demo-audio.mp3`.
- `out/` - local render outputs.
- `tts_cache/`, `tts_work/` - audio cache and temporary segment work directories.

## Requirements

- Python 3.10+
- FFmpeg and FFprobe on `PATH`
- ElevenLabs API key in `ELEVENLABS_API_KEY`
- Python package: `requests`
- Node dependencies for Remotion

```powershell
pip install requests
npm install

$env:ELEVENLABS_API_KEY = "your_key_here"
$env:Path += ";C:\ffmpeg\bin"
```

## Lesson Format

Lesson scripts contain spoken text plus metadata tags:

```xml
<lang code="zh" />
<lang code="en" />
<lang code="de" />
<lang code="auto" />
<break time="3.0s" />
```

Language tags are removed before TTS. Break tags become local silence segments. Repeated full speech blocks are cached as complete audio snippets; the pipeline never stitches cached words into new sentences.

## Curriculum Workflow

Validate all courses:

```powershell
python curriculum\tools\validate_lessons.py `
  curriculum\courses\A1_German_TTS_Lesson_Scripts `
  curriculum\courses\B1_English_TTS_Lesson_Scripts `
  curriculum\courses\B2_English_TTS_Lesson_Scripts `
  --strict
```

Apply the current lesson formatting/rebuild tools:

```powershell
python curriculum\tools\standardize_lessons.py
python curriculum\tools\rebuild_english_lessons.py
python curriculum\tools\refresh_validation_summaries.py
```

## Audio Workflow

Dry-run one lesson before spending TTS credits:

```powershell
python audio\generate_lesson_mp3.py `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.txt `
  --voice-id YOUR_VOICE_ID `
  --teacher-language zh `
  --target-language en `
  --dry-run
```

Generate one full MP3 and manifest:

```powershell
python audio\generate_lesson_mp3.py `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.txt `
  --voice-id YOUR_VOICE_ID `
  --model-id eleven_multilingual_v2 `
  --max-chars 350 `
  --teacher-language zh `
  --teacher-speech-tempo 1.0 `
  --target-language en `
  --target-speech-tempo 0.88 `
  --speech-tempo 1.0 `
  --elevenlabs-speed 1.0 `
  --break-multiplier 1.0 `
  --stability 0.65 `
  --similarity-boost 0.80 `
  --style 0.0 `
  --normalize-loudness
```

Without `--output`, the MP3 and `.manifest.json` are written beside the lesson script. The completed manifest is important: it records exact TTS settings, cache keys, rendered silence, measured speech/silence durations, segment start/end times, and the final MP3 hash.

Generate every lesson in a course folder:

```powershell
$folder = "curriculum\courses\B2_English_TTS_Lesson_Scripts"
$voiceId = "YOUR_VOICE_ID"

$lessons = Get-ChildItem -Path $folder -Filter "B2_Lesson_*.txt" |
  Where-Object { $_.BaseName -notlike "*_example" } |
  Sort-Object Name

foreach ($lesson in $lessons) {
  python audio\generate_lesson_mp3.py `
    $lesson.FullName `
    --voice-id $voiceId `
    --model-id eleven_multilingual_v2 `
    --max-chars 350 `
    --teacher-language zh `
    --teacher-speech-tempo 1.0 `
    --target-language en `
    --target-speech-tempo 0.88 `
    --elevenlabs-speed 1.0 `
    --break-multiplier 1.0 `
    --normalize-loudness

  if ($LASTEXITCODE -ne 0) {
    throw "Generation failed for $($lesson.Name)."
  }
}
```

For A1 German, use `--teacher-language en --target-language de`.

## FFmpeg Subtitle/Video Workflow

Generate SRT and flowing ASS subtitles from a completed manifest:

```powershell
python video\ffmpeg\generate_subtitles.py `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.manifest.json
```

Render a lesson over a static image:

```powershell
python video\ffmpeg\render_lesson_video.py `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.mp3 `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.ass `
  --background-image background.jpg `
  --output out\B2_Lesson_01_Opinions_and_Debate.mp4
```

Render over a looping video:

```powershell
python video\ffmpeg\render_lesson_video.py `
  lesson.mp3 `
  lesson.ass `
  --background-video background_loop.mp4 `
  --output out\lesson.mp4
```

Use `--preview-start` and `--preview-duration` to render short styling checks before full episodes.

## Remotion Waveform Video Workflow

The Remotion video uses the same audio plus manifest-derived subtitle timings. This keeps Mandarin and target-language text synchronized with the exact stitched audio segments.

Copy or generate the episode audio into `public/` for Remotion:

```powershell
Copy-Item `
  public\demo-audio.mp3
```

Create 30-second demo Remotion props from the measured manifest:

```powershell
python video\manifest_to_remotion_props.py `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.manifest.json `
  --output video\remotion\combined-30s-props.json `
  --audio-src demo-audio.mp3 `
  --style-props video\remotion\podcast-final-style.json `
  --preview-duration 30
```

For a full episode, omit `--preview-duration`; the converter uses the completed manifest duration.

Render the 30-second combined demo:

```powershell
npm run remotion:render:combined30
```

Output: `out\podcast-combined-30s-demo.mp4`.

The render command uses `video/render_remotion_video.py`, which also writes a sidecar video manifest:

```text
out\podcast-combined-30s-demo.video.manifest.json
```

That sidecar records the render command, Remotion entry/composition, props hash, audio manifest hash, props snapshot, output hash, output probe data, timestamp, and git state.

The reusable visual settings live in:

```text
video\remotion\podcast-final-style.json
```

Pass a different file with `--style-props` when creating Remotion props if you want a different waveform/layout preset.

Iterate on the standalone waveform ribbon:

```powershell
npm run remotion:still:ribbon
npm run remotion:render:ribbon
```

Useful standalone ribbon settings live in `video/remotion/ribbon-still-props.json`. Production `PodcastFinal` settings live in `video/remotion/podcast-final-style.json`.

- `width`, `height` - ribbon canvas size.
- `amplitude`, `gain`, `minVolume` - how strongly audio drives movement.
- `smoothFrames`, `modeSpeed`, `centerDrift`, `rhythmSpeedInfluence` - calmness vs. nervousness.
- `opacity`, `glowOpacity`, `gradientPeak`, `gradientSpread`, `gradientHardness`, `colorPairs` - color intensity and glow.

## Script Reference

### `audio/generate_lesson_mp3.py`

Parses a tagged lesson, generates/caches complete speech blocks with ElevenLabs, renders pauses locally, applies tempo and optional loudness normalization, stitches the final MP3, and writes a reproducibility manifest.

Key options:

- `--voice-id`, `--model-id`, `--output`
- `--stability`, `--similarity-boost`, `--style`
- `--elevenlabs-speed` controls ElevenLabs `voice_settings.speed`; default `1.0`
- `--speaker-boost` enables ElevenLabs `voice_settings.use_speaker_boost`; default is off
- `--teacher-language`, `--teacher-speech-tempo`
- `--target-language`, `--target-speech-tempo`
- `--speech-tempo` applies local FFmpeg tempo processing after ElevenLabs generation
- `--seed` (`--seed -1` omits the seed)
- `--min-break`, `--break-multiplier`
- `--normalize-loudness`, `--loudness-target-i`, `--loudness-target-tp`, `--loudness-target-lra`
- `--cache-dir`, `--work-dir`, `--keep-work`
- `--manifest`, `--no-manifest`, `--dry-run`

Example with API-side speed and speaker boost enabled:

```powershell
python audio\generate_lesson_mp3.py `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.txt `
  --voice-id YOUR_VOICE_ID `
  --model-id eleven_multilingual_v2 `
  --teacher-language zh `
  --target-language en `
  --elevenlabs-speed 0.95 `
  --speaker-boost `
  --speech-tempo 1.0 `
  --normalize-loudness
```

### `curriculum/tools/validate_lessons.py`

Validates lesson scripts. Useful options: `--strict`, `--json`, `--max-break`, `--max-chars`.

### `video/ffmpeg/generate_subtitles.py`

Reads a completed manifest and writes `.srt` plus flowing `.ass` subtitles. Useful options: `--srt-output`, `--ass-output`, `--languages`, `--srt-speech-only`, `--no-srt`, `--no-ass`.

### `video/ffmpeg/render_lesson_video.py`

Uses FFmpeg to burn ASS subtitles over a static image or looping video. Useful options: `--background-image`, `--background-video`, `--preview-start`, `--preview-duration`, `--crf`, `--preset`.

### `video/manifest_to_remotion_props.py`

Converts a completed manifest into Remotion `PodcastFinal` props with exact segment timings. Omit `--preview-duration` for a full episode, or set it for short demos. Use `--style-props` to pass reusable waveform/layout settings instead of editing the converter.

### `video/render_remotion_video.py`

Renders Remotion through a Python wrapper and writes a `.video.manifest.json` sidecar beside the MP4. Use this for production renders so video settings are reproducible like audio settings.

## Current Direction

The project is ready for full-episode video generation once we add a production Remotion props command for full lesson duration and settle the final visual layout. The manifest is the timing source of truth for both subtitles and waveform synchronization.
