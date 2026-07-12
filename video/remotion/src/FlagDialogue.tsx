import React, {useMemo} from 'react';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/700.css';
import {useAudioData, visualizeAudio} from '@remotion/media-utils';
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {z} from 'zod';
import {mediaSource} from './mediaSource';

const subtitleEntrySchema = z.object({
  start: z.number().min(0),
  end: z.number().positive(),
  text: z.string(),
  lang: z.string().default('en'),
});

export const flagDialogueSchema = z.object({
  audioSrc: z.string(),
  videoSrc: z.string().optional(),
  teacherFlagSrc: z.string(),
  targetFlagSrc: z.string(),
  teacherLanguage: z.string().default('zh'),
  targetLanguage: z.string().default('en'),
  durationInSeconds: z.number().positive().default(10),
  subtitleEntries: z.array(subtitleEntrySchema).default([]),
  backgroundColor: z.string().default('#ffffff'),
  flagSize: z.number().positive().default(132),
  flagGap: z.number().nonnegative().default(34),
  haloMaxScale: z.number().positive().default(2.3),
  haloMinScale: z.number().positive().default(1.45),
  haloGain: z.number().positive().default(22),
  haloSmoothFrames: z.number().int().min(0).default(18),
  haloFadeSeconds: z.number().nonnegative().default(0.32),
  haloVolumeThreshold: z.number().nonnegative().default(0.012),
  haloNormalizationOffset: z.number().default(0.04),
  haloNormalizationRange: z.number().positive().default(0.74),
  haloMinVisibleVolume: z.number().min(0).max(1).default(0),
  haloVolumePower: z.number().positive().default(0.82),
  haloMinOpacity: z.number().min(0).max(1).default(0.42),
  haloOpacityRange: z.number().min(0).max(1).default(0.06),
  haloBlobPoints: z.number().int().min(12).default(72),
  haloBlobBaseRadius: z.number().positive().default(72),
  haloBlobVarianceBase: z.number().nonnegative().default(0.5),
  haloBlobVarianceVolume: z.number().nonnegative().default(0.75),
  haloBlobMotionDivisor: z.number().positive().default(30),
  haloBlurStdDeviation: z.number().nonnegative().default(3),
  haloBlurOpacity: z.number().min(0).max(1).default(0.04),
  haloGradientRadius: z.number().positive().default(76),
  haloGradientInnerColor: z.string().default('#777777'),
  haloGradientInnerOpacity: z.number().min(0).max(1).default(1),
  haloGradientMidColor: z.string().default('#777777'),
  haloGradientMidOffset: z.number().min(0).max(100).default(84),
  haloGradientMidOpacity: z.number().min(0).max(1).default(1),
  haloGradientOuterColor: z.string().default('#777777'),
  haloGradientOuterOpacity: z.number().min(0).max(1).default(0),
  haloGradientFillOpacity: z.number().min(0).max(1).default(1),
  lineY: z.number().nonnegative().default(540),
  flagsLeft: z.number().nonnegative().default(250),
  textLeft: z.number().nonnegative().default(660),
  textWidth: z.number().positive().default(1010),
  chineseTextFontSize: z.number().positive().default(48),
  defaultTextFontSize: z.number().positive().default(52),
  textFontWeight: z.number().positive().default(700),
  chineseTextLineHeight: z.number().positive().default(1.22),
  defaultTextLineHeight: z.number().positive().default(1.14),
  activeFlagShadow: z.string().default('0 12px 34px rgba(0, 0, 0, 0.18)'),
  inactiveFlagShadow: z.string().default('0 8px 22px rgba(0, 0, 0, 0.10)'),
  renderAudio: z.boolean().default(true),
});

export type FlagDialogueProps = z.infer<typeof flagDialogueSchema>;

const clamp = (value: number, min: number, max: number) => {
  return Math.min(max, Math.max(min, value));
};

const smootherStep = (value: number) => {
  const x = clamp(value, 0, 1);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const average = (values: number[]) => {
  if (values.length === 0) {
    return 0;
  }

  return values.reduce((total, value) => total + value, 0) / values.length;
};

const languageMatches = (language: string, roleLanguage: string) => {
  const normalizedLanguage = language.toLowerCase();
  const normalizedRole = roleLanguage.toLowerCase();

  if (normalizedRole.includes('-')) {
    return normalizedLanguage === normalizedRole;
  }

  return normalizedLanguage.split('-', 1)[0] === normalizedRole;
};

const fontForLanguage = (language: string) => {
  if (language.toLowerCase().startsWith('zh')) {
    return '"Microsoft YaHei", "Noto Sans SC", "PingFang SC", Inter, Arial, sans-serif';
  }

  return 'Inter, Arial, Helvetica, sans-serif';
};

const blobPath = (
  volume: number,
  frame: number,
  points: number,
  baseRadius: number,
  varianceBase: number,
  varianceVolume: number,
  motionDivisor: number
) => {
  const center = 100;
  const variance = varianceBase + volume * varianceVolume;
  const motion = frame / motionDivisor;
  const coordinates: {x: number; y: number}[] = [];

  for (let index = 0; index < points; index++) {
    const angle = (Math.PI * 2 * index) / points;
    const radius =
      baseRadius +
      Math.sin(angle * 3 + motion * 1.2) * variance +
      Math.sin(angle * 5 - motion * 1.85) * variance * 0.45 +
      Math.cos(angle * 7 + motion * 0.95) * variance * 0.25;
    const x = center + Math.cos(angle) * radius;
    const y = center + Math.sin(angle) * radius;
    coordinates.push({x, y});
  }

  const commands = coordinates.map((point, index) => {
    const next = coordinates[(index + 1) % coordinates.length];
    const controlX = (point.x + next.x) / 2;
    const controlY = (point.y + next.y) / 2;

    if (index === 0) {
      return `M ${point.x.toFixed(2)},${point.y.toFixed(2)} Q ${point.x.toFixed(2)},${point.y.toFixed(2)} ${controlX.toFixed(2)},${controlY.toFixed(2)}`;
    }

    return `T ${controlX.toFixed(2)},${controlY.toFixed(2)}`;
  });

  return `${commands.join(' ')} Z`;
};

const BlobHalo: React.FC<{
  activity: number;
  volume: number;
  size: number;
  maxScale: number;
  minScale: number;
  volumeThreshold: number;
  normalizationOffset: number;
  normalizationRange: number;
  minVisibleVolume: number;
  volumePower: number;
  minOpacity: number;
  opacityRange: number;
  blobPoints: number;
  blobBaseRadius: number;
  blobVarianceBase: number;
  blobVarianceVolume: number;
  blobMotionDivisor: number;
  blurStdDeviation: number;
  blurOpacity: number;
  gradientRadius: number;
  gradientInnerColor: string;
  gradientInnerOpacity: number;
  gradientMidColor: string;
  gradientMidOffset: number;
  gradientMidOpacity: number;
  gradientOuterColor: string;
  gradientOuterOpacity: number;
  gradientFillOpacity: number;
  left: number;
  top: number;
  frame: number;
}> = ({
  activity,
  volume,
  size,
  maxScale,
  minScale,
  volumeThreshold,
  normalizationOffset,
  normalizationRange,
  minVisibleVolume,
  volumePower,
  minOpacity,
  opacityRange,
  blobPoints,
  blobBaseRadius,
  blobVarianceBase,
  blobVarianceVolume,
  blobMotionDivisor,
  blurStdDeviation,
  blurOpacity,
  gradientRadius,
  gradientInnerColor,
  gradientInnerOpacity,
  gradientMidColor,
  gradientMidOffset,
  gradientMidOpacity,
  gradientOuterColor,
  gradientOuterOpacity,
  gradientFillOpacity,
  left,
  top,
  frame,
}) => {
  const active = activity > 0.01;
  const normalizedVolume = clamp(
    (volume - normalizationOffset) / normalizationRange,
    0,
    1
  );
  const volumePresence = active
    ? smootherStep(volume / Math.max(normalizationOffset, volumeThreshold))
    : 0;
  const visibleVolume =
    (normalizedVolume + minVisibleVolume * (1 - normalizedVolume)) * volumePresence;
  const haloVolume = Math.pow(visibleVolume, volumePower);
  const haloScale =
    1 +
    (minScale - 1) * volumePresence +
    haloVolume * Math.max(0, maxScale - minScale);
  const haloSize = size * haloScale;
  const haloOpacity =
    (minOpacity + haloVolume * opacityRange) * activity * volumePresence;
  const path = useMemo(
    () =>
      blobPath(
        haloVolume,
        frame,
        blobPoints,
        blobBaseRadius,
        blobVarianceBase,
        blobVarianceVolume,
        blobMotionDivisor
      ),
    [
      blobBaseRadius,
      blobMotionDivisor,
      blobPoints,
      blobVarianceBase,
      blobVarianceVolume,
      frame,
      haloVolume,
    ]
  );

  if (activity <= 0.01 || volumePresence <= 0.001) {
    return null;
  }

  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        width: size,
        height: size,
        transform: 'translateY(-50%)',
        zIndex: 0,
        pointerEvents: 'none',
      }}
    >
      <svg
        viewBox="0 0 200 200"
        style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          width: haloSize,
          height: haloSize,
          transform: 'translate(-50%, -50%)',
          opacity: haloOpacity,
          overflow: 'visible',
        }}
      >
        <defs>
          <filter id="flag-dialogue-halo-blur" x="-35%" y="-35%" width="170%" height="170%">
            <feGaussianBlur stdDeviation={blurStdDeviation} />
          </filter>
          <radialGradient
            id="flag-dialogue-halo-gradient"
            cx="50%"
            cy="50%"
            r={`${gradientRadius}%`}
          >
            <stop
              offset="0%"
              stopColor={gradientInnerColor}
              stopOpacity={gradientInnerOpacity}
            />
            <stop
              offset={`${gradientMidOffset}%`}
              stopColor={gradientMidColor}
              stopOpacity={gradientMidOpacity}
            />
            <stop
              offset="100%"
              stopColor={gradientOuterColor}
              stopOpacity={gradientOuterOpacity}
            />
          </radialGradient>
        </defs>
        <path
          d={path}
          fill="#b0b0b0"
          opacity={blurOpacity}
          filter="url(#flag-dialogue-halo-blur)"
        />
        <path
          d={path}
          fill="url(#flag-dialogue-halo-gradient)"
          opacity={gradientFillOpacity}
        />
      </svg>
    </div>
  );
};

const FlagImage: React.FC<{
  src: string;
  active: boolean;
  size: number;
  left: number;
  top: number;
  activeShadow: string;
  inactiveShadow: string;
}> = ({src, active, size, left, top, activeShadow, inactiveShadow}) => {
  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        width: size,
        height: size,
        transform: 'translateY(-50%)',
        zIndex: 2,
      }}
    >
      <Img
        src={src}
        style={{
          position: 'absolute',
          inset: 0,
          width: size,
          height: size,
          borderRadius: '50%',
          objectFit: 'cover',
          boxShadow: active ? activeShadow : inactiveShadow,
        }}
      />
    </div>
  );
};

const activityForLanguage = (
  entries: z.infer<typeof subtitleEntrySchema>[],
  currentTime: number,
  roleLanguage: string,
  fadeSeconds: number,
) => {
  let activity = 0;

  for (const entry of entries) {
    if (!languageMatches(entry.lang, roleLanguage)) {
      continue;
    }

    if (currentTime >= entry.start && currentTime < entry.end) {
      activity = Math.max(activity, 1);
      continue;
    }

    if (currentTime >= entry.end && currentTime < entry.end + fadeSeconds) {
      activity = Math.max(activity, 1 - (currentTime - entry.end) / fadeSeconds);
      continue;
    }

    if (currentTime < entry.start && currentTime > entry.start - fadeSeconds) {
      activity = Math.max(activity, 1 - (entry.start - currentTime) / fadeSeconds);
    }
  }

  return clamp(activity, 0, 1);
};

export const FlagDialogue: React.FC<FlagDialogueProps> = ({
  audioSrc,
  videoSrc,
  teacherFlagSrc,
  targetFlagSrc,
  teacherLanguage,
  targetLanguage,
  subtitleEntries,
  backgroundColor,
  flagSize,
  flagGap,
  haloMaxScale,
  haloMinScale,
  haloGain,
  haloSmoothFrames,
  haloFadeSeconds,
  haloVolumeThreshold,
  haloNormalizationOffset,
  haloNormalizationRange,
  haloMinVisibleVolume,
  haloVolumePower,
  haloMinOpacity,
  haloOpacityRange,
  haloBlobPoints,
  haloBlobBaseRadius,
  haloBlobVarianceBase,
  haloBlobVarianceVolume,
  haloBlobMotionDivisor,
  haloBlurStdDeviation,
  haloBlurOpacity,
  haloGradientRadius,
  haloGradientInnerColor,
  haloGradientInnerOpacity,
  haloGradientMidColor,
  haloGradientMidOffset,
  haloGradientMidOpacity,
  haloGradientOuterColor,
  haloGradientOuterOpacity,
  haloGradientFillOpacity,
  lineY,
  flagsLeft,
  textLeft,
  textWidth,
  chineseTextFontSize,
  defaultTextFontSize,
  textFontWeight,
  chineseTextLineHeight,
  defaultTextLineHeight,
  activeFlagShadow,
  inactiveFlagShadow,
  renderAudio,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const resolvedAudioSrc = mediaSource(audioSrc);
  const resolvedVideoSrc = videoSrc ? mediaSource(videoSrc) : undefined;
  const resolvedTeacherFlagSrc = mediaSource(teacherFlagSrc);
  const resolvedTargetFlagSrc = mediaSource(targetFlagSrc);
  const audioData = useAudioData(resolvedAudioSrc);
  const currentTime = frame / fps;

  const activeSubtitleIndex = subtitleEntries.findIndex(
    (entry) => currentTime >= entry.start && currentTime < entry.end
  );
  const activeSubtitle =
    activeSubtitleIndex >= 0 ? subtitleEntries[activeSubtitleIndex] : undefined;
  const previousSubtitles = activeSubtitle
    ? subtitleEntries.slice(Math.max(0, activeSubtitleIndex - 2), activeSubtitleIndex)
    : [];
  const nextSubtitles = activeSubtitle
    ? subtitleEntries.slice(activeSubtitleIndex + 1, activeSubtitleIndex + 3)
    : [];
  const activeLanguage = activeSubtitle?.lang ?? '';
  const teacherActive =
    activeSubtitle !== undefined && languageMatches(activeLanguage, teacherLanguage);
  const targetActive =
    activeSubtitle !== undefined && languageMatches(activeLanguage, targetLanguage);
  const teacherActivity = activityForLanguage(
    subtitleEntries,
    currentTime,
    teacherLanguage,
    haloFadeSeconds
  );
  const targetActivity = activityForLanguage(
    subtitleEntries,
    currentTime,
    targetLanguage,
    haloFadeSeconds
  );

  const volume = useMemo(() => {
    if (!audioData || !activeSubtitle) {
      return 0;
    }

    let total = 0;
    let weightTotal = 0;

    for (let offset = -haloSmoothFrames; offset <= haloSmoothFrames; offset++) {
      const currentFrame = Math.max(0, frame + offset);
      const weight = haloSmoothFrames + 1 - Math.abs(offset);
      const visualization = visualizeAudio({
        fps,
        frame: currentFrame,
        audioData,
        numberOfSamples: 32,
      });

      total += average(visualization.slice(0, 16)) * weight;
      weightTotal += weight;
    }

    return clamp((total / weightTotal) * haloGain, 0, 1);
  }, [activeSubtitle, audioData, fps, frame, haloGain, haloSmoothFrames]);

  const subtitleLineStyle = {
    position: 'absolute' as const,
    left: textLeft,
    width: textWidth,
    color: '#111111',
    letterSpacing: 0,
    overflowWrap: 'break-word' as const,
    whiteSpace: 'normal' as const,
  };
  const currentTextStyle = {
    ...subtitleLineStyle,
    top: lineY,
    transform: 'translateY(-50%)',
    fontFamily: fontForLanguage(activeSubtitle?.lang ?? targetLanguage),
    fontSize: activeSubtitle?.lang?.toLowerCase().startsWith('zh')
      ? chineseTextFontSize
      : defaultTextFontSize,
    fontWeight: textFontWeight,
    lineHeight: activeSubtitle?.lang?.toLowerCase().startsWith('zh')
      ? chineseTextLineHeight
      : defaultTextLineHeight,
  };
  const contextTextStyleForLang = (language: string) => {
    const isChinese = language.toLowerCase().startsWith('zh');

    return {
      fontFamily: fontForLanguage(language),
      fontSize: isChinese ? 30 : 29,
      fontWeight: 500,
      lineHeight: isChinese ? 1.22 : 1.15,
    };
  };

  return (
    <AbsoluteFill style={{backgroundColor}}>
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

      <AbsoluteFill>
        <BlobHalo
          activity={teacherActivity}
          volume={volume}
          size={flagSize}
          maxScale={haloMaxScale}
          minScale={haloMinScale}
          volumeThreshold={haloVolumeThreshold}
          normalizationOffset={haloNormalizationOffset}
          normalizationRange={haloNormalizationRange}
          minVisibleVolume={haloMinVisibleVolume}
          volumePower={haloVolumePower}
          minOpacity={haloMinOpacity}
          opacityRange={haloOpacityRange}
          blobPoints={haloBlobPoints}
          blobBaseRadius={haloBlobBaseRadius}
          blobVarianceBase={haloBlobVarianceBase}
          blobVarianceVolume={haloBlobVarianceVolume}
          blobMotionDivisor={haloBlobMotionDivisor}
          blurStdDeviation={haloBlurStdDeviation}
          blurOpacity={haloBlurOpacity}
          gradientRadius={haloGradientRadius}
          gradientInnerColor={haloGradientInnerColor}
          gradientInnerOpacity={haloGradientInnerOpacity}
          gradientMidColor={haloGradientMidColor}
          gradientMidOffset={haloGradientMidOffset}
          gradientMidOpacity={haloGradientMidOpacity}
          gradientOuterColor={haloGradientOuterColor}
          gradientOuterOpacity={haloGradientOuterOpacity}
          gradientFillOpacity={haloGradientFillOpacity}
          left={flagsLeft}
          top={lineY}
          frame={frame}
        />
        <BlobHalo
          activity={targetActivity}
          volume={volume}
          size={flagSize}
          maxScale={haloMaxScale}
          minScale={haloMinScale}
          volumeThreshold={haloVolumeThreshold}
          normalizationOffset={haloNormalizationOffset}
          normalizationRange={haloNormalizationRange}
          minVisibleVolume={haloMinVisibleVolume}
          volumePower={haloVolumePower}
          minOpacity={haloMinOpacity}
          opacityRange={haloOpacityRange}
          blobPoints={haloBlobPoints}
          blobBaseRadius={haloBlobBaseRadius}
          blobVarianceBase={haloBlobVarianceBase}
          blobVarianceVolume={haloBlobVarianceVolume}
          blobMotionDivisor={haloBlobMotionDivisor}
          blurStdDeviation={haloBlurStdDeviation}
          blurOpacity={haloBlurOpacity}
          gradientRadius={haloGradientRadius}
          gradientInnerColor={haloGradientInnerColor}
          gradientInnerOpacity={haloGradientInnerOpacity}
          gradientMidColor={haloGradientMidColor}
          gradientMidOffset={haloGradientMidOffset}
          gradientMidOpacity={haloGradientMidOpacity}
          gradientOuterColor={haloGradientOuterColor}
          gradientOuterOpacity={haloGradientOuterOpacity}
          gradientFillOpacity={haloGradientFillOpacity}
          left={flagsLeft + flagSize + flagGap}
          top={lineY}
          frame={frame}
        />
        <FlagImage
          src={resolvedTeacherFlagSrc}
          active={teacherActive}
          size={flagSize}
          left={flagsLeft}
          top={lineY}
          activeShadow={activeFlagShadow}
          inactiveShadow={inactiveFlagShadow}
        />
        <FlagImage
          src={resolvedTargetFlagSrc}
          active={targetActive}
          size={flagSize}
          left={flagsLeft + flagSize + flagGap}
          top={lineY}
          activeShadow={activeFlagShadow}
          inactiveShadow={inactiveFlagShadow}
        />

        {previousSubtitles.map((subtitle, index) => {
          const distanceFromCurrent = previousSubtitles.length - index;

          return (
            <div
              key={`previous-${subtitle.start}-${index}`}
              style={{
                ...subtitleLineStyle,
                ...contextTextStyleForLang(subtitle.lang),
                top: lineY - 92 * distanceFromCurrent,
                opacity: index === previousSubtitles.length - 1 ? 0.42 : 0.25,
                transform: 'translateY(-50%)',
              }}
            >
              {subtitle.text}
            </div>
          );
        })}

        {activeSubtitle ? (
          <div style={currentTextStyle}>{activeSubtitle.text}</div>
        ) : null}

        {nextSubtitles.map((subtitle, index) => (
          <div
            key={`next-${subtitle.start}-${index}`}
            style={{
              ...subtitleLineStyle,
              ...contextTextStyleForLang(subtitle.lang),
              top: lineY + 92 * (index + 1),
              opacity: index === 0 ? 0.42 : 0.25,
              transform: 'translateY(-50%)',
            }}
          >
            {subtitle.text}
          </div>
        ))}
      </AbsoluteFill>

      {renderAudio ? <Audio src={resolvedAudioSrc} /> : null}
    </AbsoluteFill>
  );
};
