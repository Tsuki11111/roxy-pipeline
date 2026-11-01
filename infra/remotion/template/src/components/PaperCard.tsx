import type {CSSProperties, ReactNode} from 'react';
import {CLAY, FONT_FAMILY, FONT_SERIF, INK, INK_SOFT, PAPER_DEEP, PAPER_LIGHT} from '../theme';

export type PaperVariant =
  | 'note'
  | 'quote'
  | 'index'
  | 'letter'
  | 'sticky'
  | 'specimen';

export type PaperTone = 'cream' | 'sand' | 'peach' | 'sage';

interface Props {
  text?: string;
  lines?: string[];
  title?: string;
  meta?: string;
  mark?: string;
  left?: number;
  top?: number;
  width?: number;
  minHeight?: number;
  variant?: PaperVariant;
  tone?: PaperTone;
  accent?: string;
  opacity?: number;
  scale?: number;
  translateX?: number;
  translateY?: number;
  rotate?: number;
  rotateY?: number;
  reveal?: number;
  zIndex?: number;
  style?: CSSProperties;
}

const TONES: Record<PaperTone, {paper: string; border: string}> = {
  cream: {paper: PAPER_LIGHT, border: 'rgba(35,32,27,0.28)'},
  sand: {paper: PAPER_DEEP, border: 'rgba(35,32,27,0.18)'},
  peach: {paper: '#f2dccd', border: 'rgba(35,32,27,0.14)'},
  sage: {paper: '#e3e8dc', border: 'rgba(35,32,27,0.16)'},
};

const RADIUS: Record<PaperVariant, string> = {
  note: '6px 16px 8px 14px',
  quote: '4px 12px 5px 10px',
  index: '4px 8px 4px 8px',
  letter: '3px 6px 3px 6px',
  sticky: '2px 10px 3px 8px',
  specimen: '6px 18px 8px 16px',
};

const Star = ({color}: {color: string}) => (
  <svg
    width={30}
    height={30}
    viewBox="0 0 32 32"
    fill="none"
    style={{position: 'absolute', right: 22, top: 20, opacity: 0.55}}
  >
    <path
      d="M16 3v26M3 16h26M6.8 6.8l18.4 18.4M25.2 6.8 6.8 25.2"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
    />
  </svg>
);

const marked = (text: string, mark: string | undefined, accent: string): ReactNode => {
  if (!mark || !text.includes(mark)) return text;
  const parts = text.split(mark);
  return parts.map((part, index) => (
    <span key={index}>
      {part}
      {index < parts.length - 1 && (
        <span
          style={{
            background: `linear-gradient(transparent 68%, ${accent}33 68%)`,
            paddingBottom: 2,
          }}
        >
          {mark}
        </span>
      )}
    </span>
  ));
};

export const PaperCard = ({
  text,
  lines,
  title,
  meta,
  mark,
  left = 120,
  top = 130,
  width = 1040,
  minHeight = 380,
  variant = 'note',
  tone = 'cream',
  accent = CLAY,
  opacity = 1,
  scale = 1,
  translateX = 0,
  translateY = 0,
  rotate = 0,
  rotateY = 0,
  reveal = 1,
  zIndex = 8,
  style,
}: Props) => {
  const palette = TONES[tone];
  const items = lines ?? (text ? [text] : []);

  const body =
    variant === 'quote'
      ? 34
      : variant === 'sticky'
        ? 28
        : variant === 'index'
          ? 26
          : 30;

  const common: CSSProperties = {
    position: 'absolute',
    left,
    top,
    width,
    minHeight,
    padding:
      variant === 'letter'
        ? '42px 44px 38px 96px'
        : variant === 'specimen'
          ? '0 0 26px'
          : '38px 42px 36px',
    boxSizing: 'border-box',
    borderRadius: RADIUS[variant],
    background: palette.paper,
    border: `1px solid ${palette.border}`,
    boxShadow:
      '10px 14px 0 rgba(35,32,27,0.05), 0 18px 42px rgba(35,32,27,0.09)',
    transform: `perspective(1400px) translate(${translateX}px, ${translateY}px) scale(${scale}) rotate(${rotate}deg) rotateY(${rotateY}deg)`,
    transformOrigin: 'center center',
    opacity,
    zIndex,
    overflow: 'hidden',
    color: INK,
    clipPath:
      reveal < 1 ? `inset(0 ${Math.max(0, (1 - reveal) * 100)}% 0 0)` : undefined,
  };

  const texture: CSSProperties = {
    position: 'absolute',
    inset: 0,
    backgroundImage:
      'radial-gradient(rgba(35,32,27,0.035) 0.6px, transparent 0.6px)',
    backgroundSize: '5px 5px',
    opacity: 0.7,
    pointerEvents: 'none',
  };

  const textStyle: CSSProperties = {
    position: 'relative',
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    fontFamily: FONT_SERIF,
    fontSize: body,
    fontWeight: 500,
    lineHeight: 1.78,
    letterSpacing: 0.4,
  };

  return (
    <div style={{...common, ...style}}>
      <div style={texture} />

      {variant === 'specimen' && (
        <div
          style={{
            position: 'relative',
            display: 'flex',
            justifyContent: 'space-between',
            padding: '24px 34px 15px',
            borderBottom: `1px solid ${palette.border}`,
            color: INK_SOFT,
            fontFamily: FONT_FAMILY,
            fontSize: 16,
            letterSpacing: 2,
          }}
        >
          <span>{title ?? '卡片样本'}</span>
          <span>{meta ?? '长文本'}</span>
        </div>
      )}

      {variant === 'quote' && (
        <div
          style={{
            position: 'relative',
            fontFamily: FONT_SERIF,
            fontSize: 120,
            lineHeight: 0.7,
            color: accent,
            opacity: 0.32,
            marginBottom: 14,
          }}
        >
          “
        </div>
      )}

      {variant === 'index' && (
        <div
          style={{
            position: 'relative',
            height: 4,
            width: 86,
            background: accent,
            marginBottom: 26,
          }}
        />
      )}

      {variant === 'letter' && (
        <div
          style={{
            position: 'absolute',
            left: 64,
            top: 36,
            bottom: 34,
            width: 1,
            background: `${accent}55`,
          }}
        />
      )}

      {title && variant !== 'specimen' && (
        <div
          style={{
            position: 'relative',
            marginBottom: 22,
            color: INK_SOFT,
            fontFamily: FONT_FAMILY,
            fontSize: 17,
            letterSpacing: 2,
          }}
        >
          {title}
        </div>
      )}

      {(variant === 'note' || variant === 'specimen') && <Star color={accent} />}

      <div
        style={{
          ...textStyle,
          padding: variant === 'specimen' ? '30px 34px 0' : 0,
        }}
      >
        {items.map((line, index) => (
          <div key={index}>{marked(line, mark, accent)}</div>
        ))}
      </div>

      {variant === 'specimen' && (
        <div
          style={{
            position: 'relative',
            display: 'flex',
            justifyContent: 'space-between',
            margin: '30px 34px 0',
            paddingTop: 14,
            borderTop: `1px solid ${palette.border}`,
            color: INK_SOFT,
            fontFamily: FONT_FAMILY,
            fontSize: 15,
            letterSpacing: 1.5,
          }}
        >
          <span>{meta ?? 'Claude style'}</span>
          <span>{items.join('').length} 字</span>
        </div>
      )}

      {variant === 'quote' && meta && (
        <div
          style={{
            position: 'relative',
            marginTop: 28,
            color: INK_SOFT,
            fontFamily: FONT_FAMILY,
            fontSize: 16,
            letterSpacing: 1.5,
          }}
        >
          {meta}
        </div>
      )}
    </div>
  );
};
