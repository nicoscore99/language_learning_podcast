import React from 'react';
import {AbsoluteFill, staticFile} from 'remotion';
import {z} from 'zod';
import {WaveformPill, waveformPillSchema} from './components/WaveformPill';

export const waveformPillStillSchema = z.object({
  audioSrc: z.string(),
  backgroundColor: z.string().default('#ffffff'),
  frame: z.number().int().min(0).default(120),
  waveform: waveformPillSchema,
});

export type WaveformPillStillProps = z.infer<typeof waveformPillStillSchema>;

const mediaSource = (src: string) => {
  if (/^(https?:|file:|data:|\/)/.test(src)) {
    return src;
  }
  return staticFile(src);
};

export const WaveformPillStill: React.FC<WaveformPillStillProps> = ({
  audioSrc,
  backgroundColor,
  waveform,
}) => {
  return (
    <AbsoluteFill style={{backgroundColor}}>
      <WaveformPill audioSrc={mediaSource(audioSrc)} {...waveform} />
    </AbsoluteFill>
  );
};
