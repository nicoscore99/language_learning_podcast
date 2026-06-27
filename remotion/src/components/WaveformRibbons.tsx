import React, {useMemo} from 'react';
import {visualizeAudio, useAudioData} from '@remotion/media-utils';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {z} from 'zod';

export const waveformRibbonsSchema = z.object({
  width: z.number().positive(),
  height: z.number().positive(),
  x: z.number(),
  y: z.number(),

  colorPairs: z
    .array(z.tuple([z.string(), z.string()]))
    .min(1)
    .default([
      ['#18C9F4', '#256BFF'],
      ['#256BFF', '#7B2EF2'],
      ['#7B2EF2', '#EC1688'],
      ['#EC1688', '#FFA24A'],
    ]),

  opacity: z.number().min(0).max(1).default(0.92),
  glowOpacity: z.number().min(0).max(1).default(0.18),

  amplitude: z.number().positive().default(74),
  gain: z.number().positive().default(5.5),
  sampleCount: z.number().int().min(24).max(240).default(140),
  smoothFrames: z.number().int().min(0).max(20).default(3),
  waveCount: z.number().positive().default(2.2),

  ribbonCount: z.number().int().min(2).max(8).default(4),
  thickness: z.number().positive().default(46),

  modeCountMin: z.number().int().min(1).max(12).default(2),
  modeCountMax: z.number().int().min(1).max(12).default(5),
  modeWidth: z.number().min(0.03).max(0.4).default(0.11),
  centerDrift: z.number().min(0).max(0.35).default(0.12),
  modeSpeed: z.number().positive().default(0.9),

  spread: z.number().min(0).max(1).default(0.14),

  /**
   * Base position of the strong second color in each ribbon.
   * 50 = middle of the ribbon.
   */
  gradientPeak: z.number().min(0).max(100).default(50),

  /**
   * How much the color peak position varies per ribbon.
   * Higher = each ribbon has its bright/strong color in a different place.
   */
  gradientSpread: z.number().min(0).max(80).default(42),

  /**
   * How much each ribbon's gradient direction varies.
   * Higher = less uniform left-to-right gradients.
   */
  gradientAngleVariance: z.number().min(0).max(100).default(55),

  /**
   * How hard the color transition is around the peak.
   * Low = soft gradients.
   * High = more extreme, punchy color bands.
   */
  gradientHardness: z.number().min(0).max(30).default(14),
});

export type WaveformRibbonsProps = z.infer<typeof waveformRibbonsSchema> & {
  audioSrc: string;
};

type Point = {
  x: number;
  y: number;
};

const clamp = (value: number, min: number, max: number) => {
  return Math.min(max, Math.max(min, value));
};

const smootherStep = (t: number) => {
  return t * t * t * (t * (t * 6 - 15) + 10);
};

const edgeEnvelope = (t: number) => {
  const left = smootherStep(clamp(t * 2, 0, 1));
  const right = smootherStep(clamp((1 - t) * 2, 0, 1));

  return left * right;
};

const fract = (x: number) => {
  return x - Math.floor(x);
};

const pseudoRandom = (seed: number) => {
  return fract(Math.sin(seed * 127.1 + 311.7) * 43758.5453123);
};

const gaussian = (x: number, center: number, sigma: number) => {
  const d = (x - center) / sigma;
  return Math.exp(-0.5 * d * d);
};

const pointsToSmoothPath = (points: Point[]) => {
  if (points.length < 2) {
    return '';
  }

  let path = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;

  for (let i = 1; i < points.length - 1; i++) {
    const current = points[i];
    const next = points[i + 1];

    const midX = (current.x + next.x) / 2;
    const midY = (current.y + next.y) / 2;

    path += ` Q ${current.x.toFixed(2)} ${current.y.toFixed(
      2
    )} ${midX.toFixed(2)} ${midY.toFixed(2)}`;
  }

  const last = points[points.length - 1];
  path += ` T ${last.x.toFixed(2)} ${last.y.toFixed(2)}`;

  return path;
};

const makeRibbonPath = ({
  width,
  height,
  sampleCount,
  volume,
  amplitude,
  thickness,
  phase,
  waveCount,
  verticalOffset,
  ribbonIndex,
  motion,
  modeCountMin,
  modeCountMax,
  modeWidth,
  centerDrift,
  modeSpeed,
}: {
  width: number;
  height: number;
  sampleCount: number;
  volume: number;
  amplitude: number;
  thickness: number;
  phase: number;
  waveCount: number;
  verticalOffset: number;
  ribbonIndex: number;
  motion: number;
  modeCountMin: number;
  modeCountMax: number;
  modeWidth: number;
  centerDrift: number;
  modeSpeed: number;
}) => {
  const centerY = height / 2;

  const safeModeMin = Math.min(modeCountMin, modeCountMax);
  const safeModeMax = Math.max(modeCountMin, modeCountMax);
  const modeRange = safeModeMax - safeModeMin + 1;

  const ribbonSeed = ribbonIndex * 100;
  const modeCount =
    safeModeMin + Math.floor(pseudoRandom(ribbonSeed + 1) * modeRange);

  const centerPoints = Array.from({length: sampleCount}, (_, index) => {
    const t = index / (sampleCount - 1);
    const envelope = edgeEnvelope(t);

    let localSum = 0;
    let weightSum = 0;

    for (let modeIndex = 0; modeIndex < modeCount; modeIndex++) {
      const seed = ribbonSeed + modeIndex * 17;

      const baseCenter = 0.12 + pseudoRandom(seed + 1) * 0.76;
      const driftPhase = pseudoRandom(seed + 2) * Math.PI * 2;
      const driftSpeed = modeSpeed * (0.7 + pseudoRandom(seed + 3) * 1.4);

      const movingCenter =
        baseCenter + Math.sin(motion * driftSpeed + driftPhase) * centerDrift;

      const clampedCenter = clamp(movingCenter, 0.06, 0.94);

      const sigma = modeWidth * (0.75 + pseudoRandom(seed + 4) * 0.9);
      const localEnvelope = gaussian(t, clampedCenter, sigma);

      const localFrequency = waveCount * (0.7 + pseudoRandom(seed + 5) * 1.8);

      const localPhase =
        phase * (0.8 + pseudoRandom(seed + 6) * 0.7) +
        pseudoRandom(seed + 7) * Math.PI * 2;

      const localAmplitude = 0.45 + pseudoRandom(seed + 8) * 0.9;

      localSum +=
        Math.sin(t * Math.PI * 2 * localFrequency + localPhase) *
        localEnvelope *
        localAmplitude;

      weightSum += localEnvelope;
    }

    const normalizedLocalSum =
      weightSum > 0 ? localSum / Math.sqrt(weightSum + 0.001) : 0;

    const y =
      centerY +
      verticalOffset * envelope +
      normalizedLocalSum * amplitude * volume * envelope;

    return {
      x: t * width,
      y,
      envelope,
    };
  });

  const top: Point[] = centerPoints.map((point) => ({
    x: point.x,
    y: point.y - thickness * volume * point.envelope,
  }));

  const bottom: Point[] = [...centerPoints].reverse().map((point) => ({
    x: point.x,
    y: point.y + thickness * volume * point.envelope,
  }));

  const bottomPathWithoutMove = pointsToSmoothPath(bottom).replace(
    /^M\s[-\d.]+\s[-\d.]+/,
    ''
  );

  return `${pointsToSmoothPath(top)} L ${bottom[0].x.toFixed(
    2
  )} ${bottom[0].y.toFixed(2)} ${bottomPathWithoutMove} Z`;
};

export const WaveformRibbons: React.FC<WaveformRibbonsProps> = ({
  audioSrc,
  width,
  height,
  x,
  y,
  colorPairs,
  opacity,
  glowOpacity,
  amplitude,
  gain,
  sampleCount,
  smoothFrames,
  waveCount,
  ribbonCount,
  thickness,
  modeCountMin,
  modeCountMax,
  modeWidth,
  centerDrift,
  modeSpeed,
  spread,
  gradientPeak,
  gradientSpread,
  gradientAngleVariance,
  gradientHardness,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const audioData = useAudioData(audioSrc);

  const volume = useMemo(() => {
    if (!audioData) {
      return 0.35;
    }

    let total = 0;
    let count = 0;

    for (let offset = -smoothFrames; offset <= smoothFrames; offset++) {
      const visualization = visualizeAudio({
        fps,
        frame: Math.max(0, frame + offset),
        audioData,
        numberOfSamples: 32,
      });

      const speechBands = visualization.slice(0, 14);

      total +=
        speechBands.reduce((sum, value) => sum + value, 0) / speechBands.length;

      count++;
    }

    return clamp((total / count) * gain, 0.18, 1);
  }, [audioData, fps, frame, gain, smoothFrames]);

  const motion = frame / fps;

  const ribbons = Array.from({length: ribbonCount}, (_, index) => {
    const centeredOffsets = [-0.12, 0.1, -0.04, 0.16, -0.18, 0.04, 0.2, -0.22];

    const layerOffset =
      centeredOffsets[index % centeredOffsets.length] * height * spread;

    return {
      id: index,
      path: makeRibbonPath({
        width,
        height,
        sampleCount,
        volume,
        amplitude: amplitude * (1 - index * 0.08),
        thickness: thickness * (1 - index * 0.07),
        phase: motion * (1.15 + index * 0.18) + index * 1.4,
        waveCount: waveCount + index * 0.2,
        verticalOffset: layerOffset,
        ribbonIndex: index,
        motion,
        modeCountMin,
        modeCountMax,
        modeWidth,
        centerDrift,
        modeSpeed,
      }),
      opacity: opacity * (1 - index * 0.08),
    };
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width,
        height,
        overflow: 'visible',
      }}
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{overflow: 'visible'}}
      >
        <defs>
          <filter id="ribbon-soft-glow" x="-20%" y="-80%" width="140%" height="260%">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feColorMatrix
              in="blur"
              type="matrix"
              values="
                1 0 0 0 0
                0 1 0 0 0
                0 0 1 0 0
                0 0 0 0.55 0
              "
            />
            <feMerge>
              <feMergeNode />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {ribbons.map((ribbon) => {
            const pair = colorPairs[ribbon.id % colorPairs.length];

            const seed = ribbon.id * 41;

            const peakOffset =
              gradientPeak + (pseudoRandom(seed + 1) - 0.5) * gradientSpread;

            const clampedPeak = clamp(peakOffset, 5, 95);

            const hardness = clamp(gradientHardness, 0, 30);

            const beforePeak = clamp(clampedPeak - hardness, 0, 100);
            const afterPeak = clamp(clampedPeak + hardness, 0, 100);

            const angleShift =
              (pseudoRandom(seed + 2) - 0.5) * gradientAngleVariance;

            const x1 = clamp(0 + angleShift, -50, 50);
            const y1 = clamp(35 - angleShift * 0.25, 0, 100);
            const x2 = clamp(100 - angleShift, 50, 150);
            const y2 = clamp(65 + angleShift * 0.25, 0, 100);

            return (
              <linearGradient
                key={`gradient-${ribbon.id}`}
                id={`ribbon-gradient-${ribbon.id}`}
                x1={`${x1}%`}
                y1={`${y1}%`}
                x2={`${x2}%`}
                y2={`${y2}%`}
              >
                <stop offset="0%" stopColor={pair[0]} />
                <stop offset={`${beforePeak}%`} stopColor={pair[0]} />
                <stop offset={`${clampedPeak}%`} stopColor={pair[1]} />
                <stop offset={`${afterPeak}%`} stopColor={pair[1]} />
                <stop offset="100%" stopColor={pair[0]} />
              </linearGradient>
            );
          })}
        </defs>

        {ribbons
          .slice()
          .reverse()
          .map((ribbon) => (
            <path
              key={`glow-${ribbon.id}`}
              d={ribbon.path}
              fill={`url(#ribbon-gradient-${ribbon.id})`}
              opacity={glowOpacity}
              filter="url(#ribbon-soft-glow)"
            />
          ))}

        {ribbons.map((ribbon) => (
          <path
            key={`ribbon-${ribbon.id}`}
            d={ribbon.path}
            fill={`url(#ribbon-gradient-${ribbon.id})`}
            opacity={ribbon.opacity}
          />
        ))}
      </svg>
    </div>
  );
};