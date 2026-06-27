import React, {useMemo} from 'react';
import {visualizeAudio, useAudioData} from '@remotion/media-utils';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {z} from 'zod';

export const waveformPillSchema = z.object({
  width: z.number().positive(),
  height: z.number().positive(),
  x: z.number(),
  y: z.number(),
  backgroundColor: z.string().default('#f1f1f1'),
  surfaceColor: z.string().default('#171717'),
  borderColor: z.string().default('#dedede'),
  colors: z.array(z.string()).min(1).max(4),
  opacity: z.number().min(0).max(1).default(0.72),
  glowOpacity: z.number().min(0).max(1).default(0.2),
  fillOpacity: z.number().min(0).max(1).default(0.22),
  amplitude: z.number().positive().default(30),
  gain: z.number().positive().default(4),
  sampleCount: z.number().int().min(8).max(96).default(36),
  smoothFrames: z.number().int().min(0).max(20).default(5),
  waveCount: z.number().positive().default(2.2),
});

type WaveformPillProps = z.infer<typeof waveformPillSchema> & {
  audioSrc: string;
};

const clamp = (value: number, min: number, max: number) => {
  return Math.min(max, Math.max(min, value));
};

const makeSmoothPath = ({
  width,
  height,
  sampleCount,
  volume,
  amplitude,
  phase,
  waveCount,
}: {
  width: number;
  height: number;
  sampleCount: number;
  volume: number;
  amplitude: number;
  phase: number;
  waveCount: number;
}) => {
  const centerY = height / 2;
  const points = Array.from({length: sampleCount}, (_, index) => {
    const t = index / (sampleCount - 1);
    const edgeFade = Math.sin(Math.PI * t);
    const lowFrequency = Math.sin(t * Math.PI * 2 * waveCount + phase);
    const secondary = 0.24 * Math.sin(t * Math.PI * 2 * (waveCount * 0.5) - phase * 0.7);
    const y = centerY - (lowFrequency + secondary) * amplitude * volume * edgeFade;
    return {x: t * width, y};
  });

  let path = `M ${points[0].x.toFixed(2)} ${centerY.toFixed(2)}`;
  for (let index = 1; index < points.length - 1; index++) {
    const current = points[index];
    const next = points[index + 1];
    const midX = (current.x + next.x) / 2;
    const midY = (current.y + next.y) / 2;
    path += ` Q ${current.x.toFixed(2)} ${current.y.toFixed(2)} ${midX.toFixed(2)} ${midY.toFixed(2)}`;
  }
  path += ` T ${width.toFixed(2)} ${centerY.toFixed(2)}`;
  return path;
};

const makeFillPath = (strokePath: string, width: number, height: number) => {
  const centerY = height / 2;
  return `${strokePath} L ${width.toFixed(2)} ${centerY.toFixed(2)} L 0 ${centerY.toFixed(2)} Z`;
};

export const WaveformPill: React.FC<WaveformPillProps> = ({
  audioSrc,
  width,
  height,
  x,
  y,
  backgroundColor,
  surfaceColor,
  borderColor,
  colors,
  opacity,
  glowOpacity,
  fillOpacity,
  amplitude,
  gain,
  sampleCount,
  smoothFrames,
  waveCount,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const audioData = useAudioData(audioSrc);

  const volume = useMemo(() => {
    if (!audioData) {
      return 0.12;
    }

    let total = 0;
    let count = 0;
    for (let offset = -smoothFrames; offset <= smoothFrames; offset++) {
      const visualization = visualizeAudio({
        fps,
        frame: Math.max(0, frame + offset),
        audioData,
        numberOfSamples: 16,
      });
      const spokenBand = visualization.slice(0, 8);
      total += spokenBand.reduce((sum, value) => sum + value, 0) / spokenBand.length;
      count++;
    }

    return clamp((total / count) * gain, 0.08, 1);
  }, [audioData, fps, frame, gain, smoothFrames]);

  const motion = frame / fps;
  const radius = height / 2;

  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width,
        height,
        borderRadius: radius,
        backgroundColor,
        border: borderColor === 'transparent' ? 'none' : `1px solid ${borderColor}`,
        boxShadow: [
          '0 42px 82px rgba(0, 0, 0, 0.18)',
          '0 16px 28px rgba(0, 0, 0, 0.10)',
          'inset 0 1px 0 rgba(255, 255, 255, 0.78)',
          'inset 0 -10px 20px rgba(0, 0, 0, 0.045)',
        ].join(', '),
        overflow: 'hidden',
        padding: 8,
      }}
    >
      <div
        style={{
          width: '100%',
          height: '100%',
          borderRadius: radius - 8,
          background: `linear-gradient(180deg, #f1f2f1 0%, ${surfaceColor} 52%, #d5d7d8 100%)`,
          boxShadow: [
            'inset 0 2px 7px rgba(255, 255, 255, 0.7)',
            'inset 0 -10px 20px rgba(0, 0, 0, 0.07)',
          ].join(', '),
          overflow: 'hidden',
        }}
      >
      <svg width={width - 16} height={height - 16} viewBox={`0 0 ${width - 16} ${height - 16}`}>
        <defs>
          <filter id="soft-wave-glow" x="-20%" y="-120%" width="140%" height="340%">
            <feGaussianBlur stdDeviation="2.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <line
          x1={14}
          x2={width - 30}
          y1={(height - 16) / 2}
          y2={(height - 16) / 2}
          stroke="#E11D2E"
          strokeWidth={2.2}
          strokeLinecap="round"
          opacity={0.96}
        />
        {colors.map((color, index) => {
          const phase = motion * (2.25 + index * 0.18) + index * 0.9;
          const path = makeSmoothPath({
            width: width - 16,
            height: height - 16,
            sampleCount,
            volume,
            amplitude: amplitude * (1 - index * 0.1),
            phase,
            waveCount: waveCount + index * 0.18,
          });
          const fillPath = makeFillPath(path, width - 16, height - 16);

          return (
            <g key={color + index}>
              {fillOpacity > 0 ? (
                <path
                  d={fillPath}
                  fill={color}
                  opacity={fillOpacity * (1 - index * 0.1)}
                />
              ) : null}
              <path
                d={path}
                fill="none"
                stroke={color}
                strokeWidth={11 - index * 0.9}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={glowOpacity * (1 - index * 0.08)}
                filter="url(#soft-wave-glow)"
              />
              <path
                d={path}
                fill="none"
                stroke={color}
                strokeWidth={5.8 - index * 0.55}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={opacity * (1 - index * 0.08)}
              />
            </g>
          );
        })}
      </svg>
      </div>
    </div>
  );
};
