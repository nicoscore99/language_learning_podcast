import React from 'react';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/700.css';
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {z} from 'zod';
import {WaveformRibbons, waveformRibbonsSchema} from './components/WaveformRibbons';
import {mediaSource} from './mediaSource';

export const podcastFinalSchema = z.object({
  audioSrc: z.string(),
  videoSrc: z.string().optional(),
  subtitleEntries: z
    .array(
      z.object({
        start: z.number().min(0),
        end: z.number().positive(),
        text: z.string(),
        lang: z.string().default('en'),
      })
    )
    .optional(),
  previousTexts: z.array(z.string()).default([
    'I understand your point, but I see it differently.',
    'From my perspective, the plan is useful but incomplete.',
  ]),
  currentText: z.string().default('The main claim needs stronger evidence.'),
  nextTexts: z.array(z.string()).default([
    'A fair debate needs more than one perspective.',
    'That assumption sounds reasonable at first.',
  ]),
  durationInSeconds: z.number().positive().default(10),
  waveform: waveformRibbonsSchema,
});

export type PodcastFinalProps = z.infer<typeof podcastFinalSchema>;

export const PodcastFinal: React.FC<PodcastFinalProps> = ({
  audioSrc,
  videoSrc,
  subtitleEntries,
  previousTexts,
  currentText,
  nextTexts,
  waveform,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const resolvedAudioSrc = mediaSource(audioSrc);
  const resolvedVideoSrc = videoSrc ? mediaSource(videoSrc) : undefined;
  const currentTime = frame / fps;
  const activeSubtitleIndex =
    subtitleEntries?.findIndex(
      (entry) => currentTime >= entry.start && currentTime < entry.end
    ) ?? -1;

  const activeSubtitle =
    subtitleEntries && activeSubtitleIndex >= 0
      ? subtitleEntries[activeSubtitleIndex]
      : undefined;

  const previous = activeSubtitle
    ? subtitleEntries!.slice(Math.max(0, activeSubtitleIndex - 2), activeSubtitleIndex)
    : previousTexts.slice(-2).map((text) => ({text, lang: 'en'}));

  const next = activeSubtitle
    ? subtitleEntries!.slice(activeSubtitleIndex + 1, activeSubtitleIndex + 3)
    : nextTexts.slice(0, 2).map((text) => ({text, lang: 'en'}));

  const displayCurrent = activeSubtitle ?? {text: currentText, lang: 'en'};

  const textStyleForLang = (lang: string, isCurrent: boolean) => {
    const isChinese = lang.toLowerCase().startsWith('zh');

    return {
      fontSize: isCurrent ? (isChinese ? 44 : 46) : isChinese ? 30 : 29,
      lineHeight: isChinese ? 1.22 : 1.15,
      fontWeight: isCurrent ? 700 : 500,
      fontFamily: isChinese
        ? '"Microsoft YaHei", "Noto Sans SC", "PingFang SC", Inter, Arial, sans-serif'
        : 'Inter, Arial, Helvetica, sans-serif',
    };
  };

  const waveformCenterY = waveform.y + waveform.height / 2;
  const textLeft = 700;
  const textWidth = 1040;

  const subtitleLineStyle = {
    width: textWidth,
    textAlign: 'left' as const,
    letterSpacing: 0,
    whiteSpace: 'normal' as const,
    overflowWrap: 'break-word' as const,
  };

  return (
    <AbsoluteFill style={{backgroundColor: 'white'}}>
      {resolvedVideoSrc ? (
        <OffthreadVideo
          src={resolvedVideoSrc}
          muted
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
      ) : null}

      <AbsoluteFill
        style={{
          fontFamily: 'Inter, Arial, Helvetica, sans-serif',
          color: '#111111',
        }}
      >
        <div>
          {previous.map((text, index) => {
            const distanceFromCurrent = previous.length - index;

            return (
              <div
                key={`previous-${index}`}
                style={{
                  ...subtitleLineStyle,
                  ...textStyleForLang(text.lang, false),
                  position: 'absolute',
                  left: textLeft,
                  top: waveformCenterY - 92 * distanceFromCurrent,
                  opacity: index === previous.length - 1 ? 0.42 : 0.25,
                  transform: 'translateY(-50%)',
                }}
              >
                {text.text}
              </div>
            );
          })}

          <div
            style={{
              ...subtitleLineStyle,
              ...textStyleForLang(displayCurrent.lang, true),
              position: 'absolute',
              left: textLeft,
              top: waveformCenterY,
              transform: 'translateY(-50%)',
            }}
          >
            {displayCurrent.text}
          </div>

          {next.map((text, index) => (
            <div
              key={`next-${index}`}
              style={{
                ...subtitleLineStyle,
                ...textStyleForLang(text.lang, false),
                position: 'absolute',
                left: textLeft,
                top: waveformCenterY + 92 * (index + 1),
                opacity: index === 0 ? 0.42 : 0.25,
                transform: 'translateY(-50%)',
              }}
            >
              {text.text}
            </div>
          ))}
        </div>
      </AbsoluteFill>

      <WaveformRibbons audioSrc={resolvedAudioSrc} {...waveform} />
      <Audio src={resolvedAudioSrc} />
    </AbsoluteFill>
  );
};
