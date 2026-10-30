import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ACCENT} from '../theme';

interface Props {
  start?: number;
  size?: number;
  left?: number;
  bottom?: number;
  opacity?: number;
}

export const RobotIcon = ({
  start = 0,
  size = 230,
  left = 50,
  bottom = 150,
  opacity = 1,
}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({
    frame: Math.max(0, frame - start),
    fps,
    config: {damping: 10, stiffness: 120, mass: 0.7},
  });
  const blink = Math.sin((frame - start) / 12) > 0.96 ? 0.18 : 1;

  return (
    <svg
      viewBox="0 0 240 240"
      style={{
        position: 'absolute',
        left: `${left}%`,
        bottom,
        width: size,
        height: size,
        transform: `translateX(-50%) translateY(${(1 - pop) * 40}px) scale(${0.8 + 0.2 * pop})`,
        opacity: Math.min(1, pop) * opacity,
        zIndex: 4,
        filter: 'drop-shadow(0 16px 16px rgba(60, 50, 110, 0.2))',
      }}
    >
      <line x1="120" y1="38" x2="120" y2="68" stroke={ACCENT} strokeWidth="8" strokeLinecap="round" />
      <circle cx="120" cy="30" r="12" fill={ACCENT} />
      <rect x="38" y="68" width="164" height="126" rx="34" fill="#fffdf7" stroke={ACCENT} strokeWidth="8" />
      <circle cx="88" cy="124" r="15" fill={ACCENT} opacity={blink} />
      <circle cx="152" cy="124" r="15" fill={ACCENT} opacity={blink} />
      <rect x="92" y="156" width="56" height="10" rx="5" fill={ACCENT} />
      <rect x="20" y="112" width="18" height="40" rx="9" fill={ACCENT} opacity="0.6" />
      <rect x="202" y="112" width="18" height="40" rx="9" fill={ACCENT} opacity="0.6" />
    </svg>
  );
};
