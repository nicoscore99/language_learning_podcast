import React from 'react';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/700.css';
import {AbsoluteFill, Audio, OffthreadVideo, staticFile} from 'remotion';
import {z} from 'zod';
import {WaveformRibbons, waveformRibbonsSchema} from './components/WaveformRibbons';

export const podcastFinalSchema = z.object({
  audioSrc: z.string(),
  videoSrc: z.string().optional(),
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

const mediaSource = (src: string) => {
  if (/^(https?:|file:|data:|\/)/.test(src)) {
    return src;
  }
  return staticFile(src);
};

export const PodcastFinal: React.FC<PodcastFinalProps> = ({
  audioSrc,
  videoSrc,
  previousTexts,
  currentText,
  nextTexts,
  waveform,
}) => {
  const resolvedAudioSrc = mediaSource(audioSrc);
  const resolvedVideoSrc = videoSrc ? mediaSource(videoSrc) : undefined;
  const previous = previousTexts.slice(-2);
  const next = nextTexts.slice(0, 2);

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
        <div
          style={{
            position: 'absolute',
            left: 700,
            top: 540,
            width: 1040,
            textAlign: 'left',
            letterSpacing: 0,
            transform: 'translateY(-50%)',
          }}
        >
          {previous.map((text, index) => (
            <div
              key={`previous-${index}`}
              style={{
                fontSize: 29,
                lineHeight: 1.18,
                fontWeight: 500,
                opacity: index === previous.length - 1 ? 0.42 : 0.25,
                marginBottom: 34,
                whiteSpace: 'nowrap',
              }}
            >
              {text}
            </div>
          ))}
          <div
            style={{
              fontSize: 46,
              lineHeight: 1.15,
              fontWeight: 700,
              marginBottom: 36,
              whiteSpace: 'nowrap',
            }}
          >
            {currentText}
          </div>
          {next.map((text, index) => (
            <div
              key={`next-${index}`}
              style={{
                fontSize: 29,
                lineHeight: 1.18,
                fontWeight: 500,
                opacity: index === 0 ? 0.42 : 0.25,
                marginTop: index === 0 ? 0 : 34,
                whiteSpace: 'nowrap',
              }}
            >
              {text}
            </div>
          ))}
        </div>
      </AbsoluteFill>

      <WaveformRibbons audioSrc={resolvedAudioSrc} {...waveform} />
      <Audio src={resolvedAudioSrc} />
    </AbsoluteFill>
  );
};
