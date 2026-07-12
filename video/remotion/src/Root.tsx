import React from 'react';
import {Composition} from 'remotion';
import {
  PodcastFinal,
  podcastFinalSchema,
  type PodcastFinalProps,
} from './PodcastFinal';
import {
  FlagDialogue,
  flagDialogueSchema,
  type FlagDialogueProps,
} from './FlagDialogue';
import {
  FlagDialogueStill,
  flagDialogueStillSchema,
  type FlagDialogueStillProps,
} from './FlagDialogueStill';
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
    ['#43d0fc', '#2f7df3'],
    ['#2f7df3', '#6848e4'],
    ['#6848e4', '#f02b99'],
    ['#f02b99', '#fca264'],
  ] as [string, string][],
  opacity: 0.9,
  glowOpacity: 0.14,
  amplitude: 72,
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
    height: 240,
    x: 0,
    y: 0,
  },
};

const ribbonsVideoProps: WaveformRibbonsVideoProps = {
  audioSrc: ribbonsStillProps.audioSrc,
  backgroundColor: '#ffffff',
  scale: 2,
  waveform: ribbonsStillProps.waveform,
};

const flagDialogueDefaults: FlagDialogueProps = {
  audioSrc: 'demo-audio.mp3',
  teacherFlagSrc:
    'video/country_flags/Flag_of_Peoples_Republic_of_China_Flat_Round-512x512.png',
  targetFlagSrc:
    'video/country_flags/Flag_of_United_States_Flat_Round-512x512.png',
  teacherLanguage: 'zh',
  targetLanguage: 'en',
  durationInSeconds: 10,
  subtitleEntries: [
    {
      start: 0,
      end: 4.5,
      lang: 'zh',
      text: '第一部分，课程介绍。',
    },
    {
      start: 4.5,
      end: 10,
      lang: 'en',
      text: 'The main claim needs stronger evidence.',
    },
  ],
  backgroundColor: '#ffffff',
  flagSize: 132,
  flagGap: 34,
  haloMaxScale: 2.3,
  haloMinScale: 1.45,
  haloGain: 22,
  haloSmoothFrames: 18,
  haloFadeSeconds: 0.32,
  haloVolumeThreshold: 0.012,
  haloNormalizationOffset: 0.04,
  haloNormalizationRange: 0.74,
  haloMinVisibleVolume: 0,
  haloVolumePower: 0.82,
  haloMinOpacity: 0.42,
  haloOpacityRange: 0.06,
  haloBlobPoints: 72,
  haloBlobBaseRadius: 72,
  haloBlobVarianceBase: 0.5,
  haloBlobVarianceVolume: 0.75,
  haloBlobMotionDivisor: 30,
  haloBlurStdDeviation: 3,
  haloBlurOpacity: 0.04,
  haloGradientRadius: 76,
  haloGradientInnerColor: '#777777',
  haloGradientInnerOpacity: 1,
  haloGradientMidColor: '#777777',
  haloGradientMidOffset: 84,
  haloGradientMidOpacity: 1,
  haloGradientOuterColor: '#777777',
  haloGradientOuterOpacity: 0,
  haloGradientFillOpacity: 1,
  lineY: 540,
  flagsLeft: 250,
  textLeft: 660,
  textWidth: 1010,
  chineseTextFontSize: 48,
  defaultTextFontSize: 52,
  textFontWeight: 700,
  chineseTextLineHeight: 1.22,
  defaultTextLineHeight: 1.14,
  activeFlagShadow: '0 12px 34px rgba(0, 0, 0, 0.18)',
  inactiveFlagShadow: '0 8px 22px rgba(0, 0, 0, 0.10)',
  renderAudio: true,
};

const flagDialogueStillDefaults: FlagDialogueStillProps = {
  ...flagDialogueDefaults,
  frame: 120,
  renderAudio: false,
};

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="PodcastFinal"
        component={PodcastFinal}
        calculateMetadata={({props}) => ({
          durationInFrames: Math.round(props.durationInSeconds * 30),
        })}
        durationInFrames={defaultProps.durationInSeconds * 30}
        fps={30}
        width={1920}
        height={1080}
        schema={podcastFinalSchema}
        defaultProps={defaultProps}
      />

      <Composition
        id="FlagDialogue"
        component={FlagDialogue}
        calculateMetadata={({props}) => ({
          durationInFrames: Math.round(props.durationInSeconds * 30),
        })}
        durationInFrames={flagDialogueDefaults.durationInSeconds * 30}
        fps={30}
        width={1920}
        height={1080}
        schema={flagDialogueSchema}
        defaultProps={flagDialogueDefaults}
      />

      <Composition
        id="FlagDialogueStill"
        component={FlagDialogueStill}
        durationInFrames={1}
        fps={30}
        width={1920}
        height={1080}
        schema={flagDialogueStillSchema}
        defaultProps={flagDialogueStillDefaults}
      />

      <Composition
        id="WaveformRibbonsStill"
        component={WaveformRibbonsStill}
        durationInFrames={1}
        fps={30}
        width={320}
        height={240}
        schema={waveformRibbonsStillSchema}
        defaultProps={ribbonsStillProps}
      />

      <Composition
        id="WaveformRibbonsVideo"
        component={WaveformRibbonsVideo}
        durationInFrames={900}
        fps={30}
        width={640}
        height={480}
        schema={waveformRibbonsVideoSchema}
        defaultProps={ribbonsVideoProps}
      />
    </>
  );
};
