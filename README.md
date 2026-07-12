# Language Learning Podcast Pipeline

This project generates language-learning podcast episodes from tagged lesson scripts. The pipeline is split into three parts:

- `curriculum/` - lesson source files, curriculum spreadsheets, style rules, and lesson QA tools.
- `audio/` - ElevenLabs/FFmpeg audio generation and reproducibility manifests.
- `video/` - subtitle generation, FFmpeg video rendering, and Remotion theme videos.

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
- `video/manifest_to_remotion_props.py` - converts a completed audio manifest into Ribbon Theme Remotion props.
- `video/remotion/` - React/TypeScript Remotion compositions and theme props.
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

## Remotion Video Themes

The Remotion video layer has two separate themes. Both use the same stitched audio and manifest-derived subtitle timings, but they use different compositions, props files, and render commands.

### Ribbon Theme

Composition: `PodcastFinal`

This is the waveform ribbon layout. It shows previous, current, and next dialogue text beside the ribbon visualization.

Copy or generate the episode audio into `public/` for Remotion:

```powershell
Copy-Item `
  public\demo-audio.mp3
```

Create 30-second Ribbon Theme props from the measured manifest:

```powershell
python video\manifest_to_remotion_props.py `
  curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.manifest.json `
  --output video\remotion\ribbon-theme-30s-props.json `
  --audio-src demo-audio.mp3 `
  --style-props video\remotion\ribbon-theme-final-props.json `
  --preview-duration 30
```

For a full episode, omit `--preview-duration`; the converter uses the completed manifest duration.

Render the 30-second Ribbon Theme demo:

```powershell
npm run remotion:ribbon:props30
npm run remotion:ribbon:render30
```

Output: `out\ribbon-theme-30s-test.mp4`.

The render command uses `video/render_remotion_video.py`, which also writes a sidecar video manifest:

```text
out\ribbon-theme-30s-test.video.manifest.json
```

That sidecar records the render command, Remotion entry/composition, props hash, audio manifest hash, props snapshot, output hash, output probe data, timestamp, and git state.

Ribbon Theme props files:

```text
video\remotion\ribbon-theme-final-props.json
video\remotion\ribbon-theme-30s-props.json
video\remotion\ribbon-theme-standalone-props.json
```

Use `ribbon-theme-final-props.json` as the reusable visual preset. Use `ribbon-theme-30s-props.json` as the generated episode test props. Use `ribbon-theme-standalone-props.json` only for isolated ribbon stills and animation tests.

Iterate on the standalone waveform ribbon:

```powershell
npm run remotion:ribbon:still
npm run remotion:ribbon:render-standalone
```

- `width`, `height` - ribbon canvas size.
- `amplitude`, `gain`, `minVolume` - how strongly audio drives movement.
- `smoothFrames`, `modeSpeed`, `centerDrift`, `rhythmSpeedInfluence` - calmness vs. nervousness.
- `opacity`, `glowOpacity`, `gradientPeak`, `gradientSpread`, `gradientHardness`, `colorPairs` - color intensity and glow.

### Flag Dialogue Theme

Composition: `FlagDialogue`

`FlagDialogue` is a separate Remotion composition for the sentence-focused flag animation. It does not use the waveform ribbon. The teacher flag appears on the left, the target-language flag appears on the right, and both sit on the same horizontal line as the current sentence. Like the ribbon composition, it shows the previous two, current, and next two sentences, with the surrounding sentences dimmed. The active language is determined from each manifest subtitle entry's `lang` value.

For the default B2 English lessons with Mandarin teacher audio:

- teacher language: `zh`
- target language: `en`
- teacher flag: China
- target flag: United States

The render is a two-step workflow:

1. Generate a props JSON file from the audio manifest.
2. Render a still image, 30-second test video, or full video from that props file.

Quick default workflow:

```powershell
npm run remotion:flag-dialogue:props30
npm run remotion:flag-dialogue:still
npm run remotion:flag-dialogue:render30

npm run remotion:flag-dialogue:propsfull
npm run remotion:flag-dialogue:renderfull
```

Outputs:

- `out/flag-dialogue-still.png`
- `out/flag-dialogue-30s-test.mp4`
- `out/flag-dialogue-full.mp4`

To tune the visual parameters, run the props generator directly, then render with the same npm scripts:

```powershell
python video\manifest_to_flag_dialogue_props.py `
  --manifest curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.manifest.json `
  --audio curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.mp3 `
  --teacher-flag video\country_flags\china.png `
  --target-flag video\country_flags\us.png `
  --output video\remotion\flag-dialogue-30s-props.json `
  --preview-duration 30 `
  --halo-min-scale 1.45 `
  --halo-max-scale 2.3 `
  --halo-smooth-frames 18 `
  --halo-normalization-offset 0.04 `
  --halo-min-visible-volume 0 `
  --halo-min-opacity 0.42 `
  --halo-opacity-range 0.06 `
  --halo-blob-motion-divisor 30 `
  --halo-blob-variance-base 0.5 `
  --halo-blob-variance-volume 0.75 `
  --halo-gradient-inner-color "#777777" `
  --halo-gradient-mid-color "#777777" `
  --halo-gradient-outer-color "#777777" `
  --halo-gradient-inner-opacity 1 `
  --halo-gradient-mid-opacity 1 `
  --halo-gradient-outer-opacity 0 `
  --halo-gradient-mid-offset 84 `
  --halo-gradient-fill-opacity 1

npm run remotion:flag-dialogue:still
npm run remotion:flag-dialogue:render30
```

For a full episode with the same tuned parameters, omit `--preview-duration` and write the full props file:

```powershell
python video\manifest_to_flag_dialogue_props.py `
  --manifest curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.manifest.json `
  --audio curriculum\courses\B2_English_TTS_Lesson_Scripts\B2_Lesson_01_Opinions_and_Debate.mp3 `
  --teacher-flag video\country_flags\china.png `
  --target-flag video\country_flags\us.png `
  --output video\remotion\flag-dialogue-full-props.json `
  --halo-min-scale 1.45 `
  --halo-max-scale 2.3 `
  --halo-smooth-frames 18 `
  --halo-normalization-offset 0.04 `
  --halo-min-visible-volume 0 `
  --halo-min-opacity 0.42 `
  --halo-opacity-range 0.06 `
  --halo-blob-motion-divisor 30 `
  --halo-blob-variance-base 0.5 `
  --halo-blob-variance-volume 0.75 `
  --halo-gradient-inner-color "#777777" `
  --halo-gradient-mid-color "#777777" `
  --halo-gradient-outer-color "#777777" `
  --halo-gradient-inner-opacity 1 `
  --halo-gradient-mid-opacity 1 `
  --halo-gradient-outer-opacity 0 `
  --halo-gradient-mid-offset 84 `
  --halo-gradient-fill-opacity 1

npm run remotion:flag-dialogue:renderfull
```

For a German target-language course, generate props with the Germany flag and target language `de`:

```powershell
python video\manifest_to_flag_dialogue_props.py `
  --manifest path\to\lesson.manifest.json `
  --output video\remotion\flag-dialogue-30s-props.json `
  --preview-duration 30 `
  --teacher-language en `
  --target-language de `
  --teacher-flag video\country_flags\us.png `
  --target-flag video\country_flags\germany.png
```

Flag dialogue parameters:

| Option | Default | Effect |
| --- | ---: | --- |
| `--background-color` | `#ffffff` | Video background color. |
| `--flag-size` | `132` | Diameter of each circular flag in pixels. |
| `--flag-gap` | `34` | Horizontal gap between the two flags. |
| `--line-y` | `540` | Vertical center line for flags and current sentence. |
| `--flags-left` | `250` | Left position of the teacher flag. |
| `--text-left` | `660` | Left position of the sentence text. |
| `--text-width` | `1010` | Maximum sentence text width. |
| `--halo-min-scale` | `1.45` | Minimum active halo diameter relative to flag size. Increase if the halo is too small. |
| `--halo-max-scale` | `2.3` | Maximum active halo diameter relative to flag size. Decrease if loud sections get too wide. |
| `--halo-gain` | `22` | Audio sensitivity for the visualization only. Higher reacts more strongly. |
| `--halo-smooth-frames` | `18` | Number of frames on each side sampled for smoothing. Higher is calmer and gives pauses a longer fade. |
| `--halo-fade-seconds` | `0.32` | Crossfade duration when switching active languages. |
| `--halo-volume-threshold` | `0.012` | Below this visual volume, the halo is hidden. |
| `--halo-normalization-offset` | `0.04` | Low-volume fade range and visual normalization floor before scaling begins. Higher makes pause fade-ins/outs longer. |
| `--halo-normalization-range` | `0.74` | Visual normalization range. Higher compresses the effect. |
| `--halo-min-visible-volume` | `0` | Optional visual volume floor while speech is active. Keep at `0` to avoid minimum-size jumps around pauses. |
| `--halo-volume-power` | `0.82` | Curve for volume-to-size response. |
| `--halo-min-opacity` | `0.42` | Base halo opacity while active. |
| `--halo-opacity-range` | `0.06` | How much opacity changes with volume. Lower makes opacity steadier. |
| `--halo-blob-points` | `72` | Number of points in the organic halo shape. Higher is smoother. |
| `--halo-blob-base-radius` | `72` | Base radius inside the SVG viewBox. Usually leave this alone. |
| `--halo-blob-variance-base` | `0.5` | Baseline non-circular shape variance. Lower is more circular. |
| `--halo-blob-variance-volume` | `0.75` | Extra shape variance as volume rises. Lower is more circular. |
| `--halo-blob-motion-divisor` | `30` | Shape drift speed. Higher is slower. |
| `--halo-blur-std-deviation` | `3` | Soft blur around the halo. Keep this low for a clean edge. |
| `--halo-blur-opacity` | `0.04` | Opacity of the blurred backing shape. |
| `--halo-gradient-radius` | `76` | Radius of the radial gradient, as a percent. Higher keeps the center flatter and fades only near the edge. |
| `--halo-gradient-inner-color` | `#777777` | Center halo color. Use the same value for inner/mid/outer for a single-color halo. |
| `--halo-gradient-inner-opacity` | `1` | Center halo opacity before global opacity is applied. |
| `--halo-gradient-mid-color` | `#777777` | Midpoint halo color. |
| `--halo-gradient-mid-offset` | `84` | Midpoint gradient stop as a percent. Higher means only the edge fades. |
| `--halo-gradient-mid-opacity` | `1` | Midpoint opacity before global opacity is applied. |
| `--halo-gradient-outer-color` | `#777777` | Edge halo color. |
| `--halo-gradient-outer-opacity` | `0` | Edge opacity before global opacity is applied. |
| `--halo-gradient-fill-opacity` | `1` | Overall opacity of the gradient fill. |
| `--chinese-text-font-size` | `48` | Current sentence font size for Chinese text. |
| `--default-text-font-size` | `52` | Current sentence font size for non-Chinese text. |
| `--text-font-weight` | `700` | Current sentence font weight. |
| `--chinese-text-line-height` | `1.22` | Chinese sentence line height. |
| `--default-text-line-height` | `1.14` | Non-Chinese sentence line height. |
| `--active-flag-shadow` | `0 12px 34px rgba(0, 0, 0, 0.18)` | CSS shadow for the active flag. Quote this value in PowerShell. |
| `--inactive-flag-shadow` | `0 8px 22px rgba(0, 0, 0, 0.10)` | CSS shadow for inactive flags. Quote this value in PowerShell. |
| `--no-render-audio` | off | Writes `renderAudio: false` into props. Usually only useful for visual-only tests. |

Useful tuning shortcuts:

- More visible at all volumes: increase `--halo-min-scale` and `--halo-min-opacity`.
- More visible without changing size: increase `--halo-min-opacity`, or use a darker single color such as `#666666`.
- Single-color halo with only edge fade: set `--halo-gradient-inner-color`, `--halo-gradient-mid-color`, and `--halo-gradient-outer-color` to the same value; keep inner/mid opacity at `1`; set `--halo-gradient-mid-offset` around `84`; leave `--halo-gradient-outer-opacity 0`.
- Very transparent center: lower `--halo-min-opacity`. Do not also lower `--halo-gradient-inner-opacity` and `--halo-gradient-fill-opacity` unless you want the halo to nearly disappear; these values multiply together.
- Less huge on loud speech: decrease `--halo-max-scale` or increase `--halo-normalization-range`.
- Less opacity change: decrease `--halo-opacity-range`.
- More circular: decrease `--halo-blob-variance-base` and `--halo-blob-variance-volume`.
- Smoother movement: increase `--halo-smooth-frames` and `--halo-blob-motion-divisor`.
- Slower fade around pauses: increase `--halo-normalization-offset`. Faster fade around pauses: decrease it.

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

Converts a completed manifest into Ribbon Theme `PodcastFinal` props with exact segment timings. Omit `--preview-duration` for a full episode, or set it for short demos. Use `--style-props video/remotion/ribbon-theme-final-props.json` to pass reusable ribbon layout settings instead of editing the converter.

### `video/manifest_to_flag_dialogue_props.py`

Converts a completed manifest into Flag Dialogue Theme `FlagDialogue` props with staged audio and flag image assets. Use `--preview-duration 30` for a short test, or omit it for the full manifest duration. Use `--teacher-language`, `--target-language`, `--teacher-flag-src`, and `--target-flag-src` to switch courses. The flag layout, halo, text, and shadow parameters are exposed as CLI options and written into the generated props JSON.

### `video/render_remotion_video.py`

Renders Remotion through a Python wrapper and writes a `.video.manifest.json` sidecar beside the MP4. Use this for production renders so video settings are reproducible like audio settings.

## Current Direction

The manifest is the timing source of truth for both subtitle display and audio-reactive Remotion theme synchronization.
