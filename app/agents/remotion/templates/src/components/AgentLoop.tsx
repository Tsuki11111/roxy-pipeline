import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ACCENT, INK} from '../theme';

const STAGGER = 6;

const STEPS = [
  {icon: '🎯', label: '目标'},
  {icon: '🗺️', label: '计划'},
  {icon: '🛠️', label: '工具'},
  {icon: '✅', label: '检查'},
];

interface Props {
  start?: number;
  top?: number;
  left?: number;
  scale?: number;
}

export const AgentLoop = ({
  start = 0,
  top = 320,
  left = 140,
  scale = 1,
}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const lineProgress = interpolate(
    frame,
    [start, start + STEPS.length * STAGGER],
    [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );

  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        width: 710,
        transform: `scale(${scale})`,
        transformOrigin: 'left top',
        zIndex: 3,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 55,
          right: 55,
          top: 55,
          height: 4,
          background: '#d8d2c5',
          transformOrigin: 'left center',
          transform: `scaleX(${lineProgress})`,
        }}
      />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          position: 'relative',
        }}
      >
        {STEPS.map((step, index) => {
          const at = start + index * STAGGER;
          const pop = spring({
            frame: Math.max(0, frame - at),
            fps,
            config: {damping: 12, stiffness: 130, mass: 0.7},
          });
          const active = frame >= at;
          const pulse = 0.5 + 0.5 * Math.sin((frame - at) / 4);
          return (
            <div
              key={step.label}
              style={{
                width: 110,
                textAlign: 'center',
                opacity: Math.min(1, pop),
                transform: `translateY(${(1 - pop) * 18}px)`,
              }}
            >
              <div
                style={{
                  position: 'relative',
                  width: 110,
                  height: 110,
                  borderRadius: '50%',
                  border: `4px solid ${active ? ACCENT : '#d8d2c5'}`,
                  background: active ? '#fff' : '#f3efe6',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 48,
                  boxShadow: active
                    ? `0 0 0 ${6 + pulse * 5}px rgba(109, 93, 252, 0.1)`
                    : 'none',
                }}
              >
                {step.icon}
              </div>
              <div
                style={{
                  marginTop: 12,
                  fontSize: 28,
                  fontWeight: 700,
                  color: active ? INK : '#8c877c',
                }}
              >
                {step.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
