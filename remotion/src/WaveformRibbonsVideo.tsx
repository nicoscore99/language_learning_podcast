import React from 'react';
import {AbsoluteFill, Audio, staticFile, useVideoConfig} from 'remotion';
import {z} from 'zod';
import {WaveformRibbons, waveformRibbonsSchema} from './components/WaveformRibbons';

export const waveformRibbonsVideoSchema = z.object({
  audioSrc: z.string(),
  backgroundColor: z.string().default('#ffffff'),
  scale: z.number().positive().default(3),
  waveform: waveformRibbonsSchema,
});

export type WaveformRibbonsVideoProps = z.infer<typeof waveformRibbonsVideoSchema>;

const mediaSource = (src: string) => {
  if (/^(https?:|file:|data:|\/)/.test(src)) {
    return src;
  }

  return staticFile(src);
};

export const WaveformRibbonsVideo: React.FC<WaveformRibbonsVideoProps> = ({
  audioSrc,
  backgroundColor,
  scale,
  waveform,
}) => {
  const {width, height} = useVideoConfig();
  const resolvedAudioSrc = mediaSource(audioSrc);
  const scaledWidth = waveform.width * scale;
  const scaledHeight = waveform.height * scale;

  return (
    <AbsoluteFill style={{backgroundColor}}>
      <div
        style={{
          position: 'absolute',
          left: (width - scaledWidth) / 2,
          top: (height - scaledHeight) / 2,
          width: waveform.width,
          height: waveform.height,
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
        }}
      >
        <WaveformRibbons
          audioSrc={resolvedAudioSrc}
          {...waveform}
          x={0}
          y={0}
        />
      </div>
      <Audio src={resolvedAudioSrc} />
    </AbsoluteFill>
  );
};
