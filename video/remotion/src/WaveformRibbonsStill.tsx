import React from 'react';
import {AbsoluteFill, Freeze} from 'remotion';
import {z} from 'zod';
import {WaveformRibbons, waveformRibbonsSchema} from './components/WaveformRibbons';
import {mediaSource} from './mediaSource';

export const waveformRibbonsStillSchema = z.object({
  audioSrc: z.string(),
  backgroundColor: z.string().default('#ffffff'),
  frame: z.number().int().min(0).default(120),
  waveform: waveformRibbonsSchema,
});

export type WaveformRibbonsStillProps = z.infer<typeof waveformRibbonsStillSchema>;

export const WaveformRibbonsStill: React.FC<WaveformRibbonsStillProps> = ({
  audioSrc,
  backgroundColor,
  frame,
  waveform,
}) => {
  const resolvedAudioSrc = mediaSource(audioSrc);

  return (
    <AbsoluteFill style={{backgroundColor}}>
      <Freeze frame={frame}>
        <WaveformRibbons audioSrc={resolvedAudioSrc} {...waveform} />
      </Freeze>
    </AbsoluteFill>
  );
};
