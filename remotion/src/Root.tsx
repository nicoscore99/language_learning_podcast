import React from 'react';
import {Composition} from 'remotion';
import {
  PodcastFinal,
  podcastFinalSchema,
  type PodcastFinalProps,
} from './PodcastFinal';
import {
  WaveformRibbonsStill,
  waveformRibbonsStillSchema,
  type WaveformRibbonsStillProps,
} from './WaveformRibbonsStill';
import {
  WaveformRibbonsVideo,
  waveformRibbonsVideoSchema,
  type WaveformRibbonsVideoProps,
} from './WaveformRibbonsVideo';

const ribbonDefaults = {
  colorPairs: [
    ['#18C9F4', '#256BFF'],
    ['#256BFF', '#7B2EF2'],
    ['#7B2EF2', '#EC1688'],
    ['#EC1688', '#FFA24A'],
  ] as [string, string][],
  opacity: 0.9,
  glowOpacity: 0.14,
  amplitude: 54,
  gain: 5.8,
  minVolume: 0.18,
  sampleCount: 140,
  smoothFrames: 3,
  waveCount: 2.4,
  trebleWaveInfluence: 0.65,
  bassThicknessInfluence: 0.5,
  rhythmSpeedInfluence: 0.35,
  ribbonCount: 4,
  thickness: 28,
  modeCountMin: 2,
  modeCountMax: 5,
  modeWidth: 0.1,
  centerDrift: 0.12,
  modeSpeed: 1,
  spread: 0.18,
  gradientPeak: 50,
  gradientSpread: 55,
  gradientAngleVariance: 75,
  gradientHardness: 18,
};

const defaultProps: PodcastFinalProps = {
  audioSrc: 'demo-audio.mp3',
  previousTexts: [
    'I understand your point, but I see it differently.',
    'From my perspective, the plan is useful but incomplete.',
  ],
  currentText: 'The main claim needs stronger evidence.',
  nextTexts: [
    'A fair debate needs more than one perspective.',
    'That assumption sounds reasonable at first.',
  ],
  durationInSeconds: 10,
  waveform: {
    ...ribbonDefaults,
    width: 520,
    height: 180,
    x: 110,
    y: 450,
  },
};

const ribbonsStillProps: WaveformRibbonsStillProps = {
  audioSrc: 'demo-audio.mp3',
  backgroundColor: '#f7f7f4',
  frame: 120,
  waveform: {
    ...ribbonDefaults,
    width: 320,
    height: 160,
    x: 0,
    y: 0,
  },
};

const ribbonsVideoProps: WaveformRibbonsVideoProps = {
  audioSrc: ribbonsStillProps.audioSrc,
  backgroundColor: '#ffffff',
  scale: 3,
  waveform: ribbonsStillProps.waveform,
};

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="PodcastFinal"
        component={PodcastFinal}
        durationInFrames={defaultProps.durationInSeconds * 30}
        fps={30}
        width={1920}
        height={1080}
        schema={podcastFinalSchema}
        defaultProps={defaultProps}
      />

      <Composition
        id="WaveformRibbonsStill"
        component={WaveformRibbonsStill}
        durationInFrames={1}
        fps={30}
        width={320}
        height={160}
        schema={waveformRibbonsStillSchema}
        defaultProps={ribbonsStillProps}
      />

      <Composition
        id="WaveformRibbonsVideo"
        component={WaveformRibbonsVideo}
        durationInFrames={900}
        fps={30}
        width={640}
        height={320}
        schema={waveformRibbonsVideoSchema}
        defaultProps={ribbonsVideoProps}
      />
    </>
  );
};
