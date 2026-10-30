import type {CSSProperties} from 'react';
import {FONT_FAMILY} from '../theme';

interface Props {
  text?: string;
  lines?: string[];
  title?: string;
  left?: number;
  top?: number;
  width?: number;
  minHeight?: number;
  rotate?: number;
  opacity?: number;
  scale?: number;
  translateX?: number;
  translateY?: number;
  accent?: string;
  zIndex?: number;
  doodles?: boolean;
}

const TAPE: CSSProperties = {
  position: 'absolute',
  width: 112,
  height: 30,
  background: 'rgba(255,236,170,0.78)',
  boxShadow: '0 4px 10px rgba(0,0,0,0.14)',
  borderRadius: 3,
};

export const Board = ({
  text,
  lines,
  title,
  left = 120,
  top = 120,
  width = 1080,
  minHeight = 430,
  rotate = -1.5,
  opacity = 1,
  scale = 1,
  translateX = 0,
  translateY = 0,
  accent = '#ffe9a8',
  zIndex = 8,
  doodles = true,
}: Props) => {
  const items = lines ?? (text ? [text] : []);

  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        width,
        minHeight,
        padding: '46px 54px 48px',
        boxSizing: 'border-box',
        borderRadius: 30,
        background:
          'linear-gradient(135deg, #3a5a52 0%, #2b4640 55%, #233b37 100%)',
        border: '10px solid #d8bb8c',
        boxShadow:
          '0 34px 80px rgba(20,30,28,0.38), inset 0 0 70px rgba(0,0,0,0.36)',
        transform: `translate(${translateX}px, ${translateY}px) scale(${scale}) rotate(${rotate}deg)`,
        transformOrigin: 'center center',
        opacity,
        zIndex,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(circle at 16% 20%, rgba(255,255,255,0.09), transparent 40%), radial-gradient(circle at 84% 82%, rgba(255,255,255,0.06), transparent 36%)',
          pointerEvents: 'none',
        }}
      />
      <div style={{...TAPE, left: -22, top: 16, transform: 'rotate(-36deg)'}} />
      <div style={{...TAPE, right: -22, bottom: 14, transform: 'rotate(-32deg)'}} />

      {doodles && (
        <>
          <svg
            width={44}
            height={44}
            viewBox="0 0 44 44"
            style={{position: 'absolute', right: 34, top: 28, opacity: 0.72}}
          >
            <path
              d="M22 4 L26.5 16 L39 16 L29 24 L33 37 L22 29 L11 37 L15 24 L5 16 L17.5 16 Z"
              fill="none"
              stroke={accent}
              strokeWidth={3}
              strokeLinejoin="round"
            />
          </svg>
          <svg
            width={40}
            height={38}
            viewBox="0 0 40 38"
            style={{position: 'absolute', left: 32, bottom: 26, opacity: 0.62}}
          >
            <path
              d="M20 34 C6 24 2 15 8 9 C13 4 20 8 20 13 C20 8 27 4 32 9 C38 15 34 24 20 34 Z"
              fill="none"
              stroke={accent}
              strokeWidth={3}
              strokeLinejoin="round"
            />
          </svg>
        </>
      )}

      {title && (
        <div
          style={{
            position: 'relative',
            display: 'inline-block',
            marginBottom: 24,
            padding: '4px 18px',
            borderRadius: 999,
            border: `2px dashed ${accent}`,
            color: accent,
            fontFamily: FONT_FAMILY,
            fontSize: 26,
            letterSpacing: 3,
            opacity: 0.9,
          }}
        >
          {title}
        </div>
      )}

      <div
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          color: '#fff9e8',
          fontFamily:
            '"YouYuan", "Yuanti SC", "Noto Sans SC", "Microsoft YaHei", sans-serif',
          fontSize: 42,
          fontWeight: 500,
          lineHeight: 1.55,
          letterSpacing: 1.5,
          textShadow: '0 0 8px rgba(255,248,220,0.3)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {items.map((line, index) => (
          <div key={index}>{line}</div>
        ))}
      </div>
    </div>
  );
};
