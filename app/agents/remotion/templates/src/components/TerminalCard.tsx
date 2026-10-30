import type {CSSProperties} from 'react';
import {useCurrentFrame} from 'remotion';

export type TerminalVariant =
  | 'terminal'
  | 'editor'
  | 'hud'
  | 'console'
  | 'snippet'
  | 'chat';

export type TerminalTone = 'navy' | 'purple' | 'mint' | 'rose';

interface Props {
  text?: string;
  lines?: string[];
  title?: string;
  filename?: string;
  left?: number;
  top?: number;
  width?: number;
  minHeight?: number;
  variant?: TerminalVariant;
  tone?: TerminalTone;
  accent?: string;
  opacity?: number;
  scale?: number;
  translateX?: number;
  translateY?: number;
  rotate?: number;
  rotateY?: number;
  reveal?: number;
  zIndex?: number;
  cursor?: boolean;
}

const TONES: Record<TerminalTone, {base: string; edge: string; accent: string}> = {
  navy: {
    base: 'linear-gradient(145deg, rgba(12,19,36,0.96), rgba(18,30,56,0.92))',
    edge: 'rgba(126,231,255,0.55)',
    accent: '#7ee7ff',
  },
  purple: {
    base: 'linear-gradient(145deg, rgba(24,16,44,0.96), rgba(39,26,64,0.92))',
    edge: 'rgba(201,167,255,0.55)',
    accent: '#c9a7ff',
  },
  mint: {
    base: 'linear-gradient(145deg, rgba(10,30,27,0.96), rgba(18,44,39,0.92))',
    edge: 'rgba(159,255,217,0.5)',
    accent: '#9fffd9',
  },
  rose: {
    base: 'linear-gradient(145deg, rgba(38,18,28,0.96), rgba(58,28,44,0.92))',
    edge: 'rgba(255,179,199,0.55)',
    accent: '#ffb3c7',
  },
};

const FONT =
  '"JetBrains Mono", "Cascadia Code", Consolas, "Noto Sans SC", "Microsoft YaHei", monospace';

const Dots = ({colors}: {colors: string[]}) => (
  <div style={{display: 'flex', gap: 8}}>
    {colors.map((color) => (
      <span
        key={color}
        style={{
          width: 12,
          height: 12,
          borderRadius: 6,
          background: color,
          boxShadow: `0 0 10px ${color}88`,
        }}
      />
    ))}
  </div>
);

const Sparkle = ({color}: {color: string}) => (
  <svg width={30} height={30} viewBox="0 0 30 30" style={{opacity: 0.8}}>
    <path
      d="M15 2 L18 12 L28 15 L18 18 L15 28 L12 18 L2 15 L12 12 Z"
      fill="none"
      stroke={color}
      strokeWidth={2}
      strokeLinejoin="round"
    />
  </svg>
);

export const TerminalCard = ({
  text,
  lines,
  title,
  filename,
  left = 120,
  top = 130,
  width = 1040,
  minHeight = 380,
  variant = 'terminal',
  tone = 'navy',
  accent,
  opacity = 1,
  scale = 1,
  translateX = 0,
  translateY = 0,
  rotate = 0,
  rotateY = 0,
  reveal = 1,
  zIndex = 8,
  cursor = true,
}: Props) => {
  const frame = useCurrentFrame();
  const items = lines ?? (text ? [text] : []);
  const palette = TONES[tone];
  const glow = accent ?? palette.accent;
  const blink = Math.floor(frame / 12) % 2 === 0;

  const header =
    variant === 'editor'
      ? filename ?? title ?? 'shot.tsx'
      : variant === 'snippet'
        ? filename ?? 'snippet.ts'
        : title ?? (variant === 'chat' ? 'AI' : 'roxy@terminal');

  const bodyStyle: CSSProperties = {
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    color: '#f2f7ff',
    fontFamily: FONT,
    fontSize: 36,
    lineHeight: 1.55,
    letterSpacing: 0.5,
    textShadow: `0 0 12px ${glow}22`,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  };

  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        width,
        minHeight,
        padding: variant === 'hud' ? '38px 46px' : '0 0 38px',
        boxSizing: 'border-box',
        borderRadius: variant === 'hud' ? 18 : 22,
        background: palette.base,
        border: `2px solid ${palette.edge}`,
        boxShadow: `0 30px 80px rgba(4,8,18,0.45), 0 0 40px ${glow}22, inset 0 1px 0 rgba(255,255,255,0.08)`,
        transform: `perspective(1400px) translate(${translateX}px, ${translateY}px) scale(${scale}) rotate(${rotate}deg) rotateY(${rotateY}deg)`,
        transformOrigin: 'center center',
        opacity,
        zIndex,
        overflow: 'hidden',
        clipPath:
          reveal < 1 ? `inset(0 ${Math.max(0, (1 - reveal) * 100)}% 0 0)` : undefined,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(circle at 18% 12%, ${glow}18, transparent 42%), linear-gradient(transparent 96%, ${glow}10 96%)`,
          backgroundSize: '100% 100%, 100% 34px',
          pointerEvents: 'none',
        }}
      />
      {variant === 'hud' && (
        <>
          <div
            style={{
              position: 'absolute',
              left: -2,
              top: -2,
              width: 42,
              height: 42,
              borderLeft: `4px solid ${glow}`,
              borderTop: `4px solid ${glow}`,
              borderTopLeftRadius: 18,
            }}
          />
          <div
            style={{
              position: 'absolute',
              right: -2,
              bottom: -2,
              width: 42,
              height: 42,
              borderRight: `4px solid ${glow}`,
              borderBottom: `4px solid ${glow}`,
              borderBottomRightRadius: 18,
            }}
          />
        </>
      )}

      {variant !== 'hud' && (
        <div
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            padding: '16px 24px',
            borderBottom: `1px solid ${palette.edge}`,
            background: 'rgba(255,255,255,0.035)',
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: 14, minWidth: 0}}>
            {variant === 'terminal' && (
              <Dots colors={['#ff7b8a', '#ffd479', '#7ee7a5']} />
            )}
            {variant === 'chat' && (
              <span
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 15,
                  background: glow,
                  color: '#0b1020',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 14,
                  fontWeight: 800,
                }}
              >
                AI
              </span>
            )}
            <span
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: glow,
                fontFamily: FONT,
                fontSize: 24,
                letterSpacing: 2,
              }}
            >
              {header}
            </span>
          </div>
          <span
            style={{
              color: 'rgba(242,247,255,0.5)',
              fontFamily: FONT,
              fontSize: 20,
              letterSpacing: 2,
            }}
          >
            {variant === 'editor' ? 'TSX' : variant === 'console' ? 'LIVE' : '●'}
          </span>
        </div>
      )}

      <div
        style={{
          position: 'relative',
          padding: variant === 'hud' ? 0 : '30px 34px 0',
        }}
      >
        {variant === 'hud' && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 20,
              color: glow,
              fontFamily: FONT,
              fontSize: 22,
              letterSpacing: 3,
            }}
          >
            <span>{header}</span>
            <Sparkle color={glow} />
          </div>
        )}

        <div style={bodyStyle}>
          {items.map((line, index) => (
            <div key={index} style={{display: 'flex', gap: 14}}>
              {variant === 'editor' && (
                <span
                  style={{
                    minWidth: 36,
                    color: 'rgba(242,247,255,0.3)',
                    textAlign: 'right',
                    fontSize: 26,
                    lineHeight: 1.75,
                  }}
                >
                  {index + 1}
                </span>
              )}
              {variant === 'console' && (
                <span style={{color: glow, fontSize: 30}}>›</span>
              )}
              {variant === 'chat' && (
                <span style={{color: glow, fontSize: 30}}>#</span>
              )}
              <span>{line}</span>
            </div>
          ))}
          {cursor && (
            <span
              style={{
                display: 'inline-block',
                width: 18,
                height: 34,
                marginLeft: 2,
                background: blink ? glow : 'transparent',
                borderRadius: 2,
                opacity: 0.9,
              }}
            />
          )}
        </div>

        {variant === 'snippet' && (
          <div
            style={{
              position: 'absolute',
              right: 30,
              top: 18,
              padding: '4px 12px',
              borderRadius: 8,
              border: `1px solid ${palette.edge}`,
              color: glow,
              fontFamily: FONT,
              fontSize: 18,
            }}
          >
            copy
          </div>
        )}
      </div>
    </div>
  );
};
