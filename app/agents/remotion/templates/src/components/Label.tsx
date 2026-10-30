import type {CSSProperties} from 'react';
import {FONT_FAMILY, INK} from '../theme';

export type LabelVariant =
  | 'pill'
  | 'tag'
  | 'callout'
  | 'note'
  | 'badge'
  | 'stamp';

interface Props {
  text?: string;
  lines?: string[];
  left: number;
  top: number;
  variant?: LabelVariant;
  rotate?: number;
  opacity?: number;
  maxWidth?: number;
  fontSize?: number;
  zIndex?: number;
}

const BASE: CSSProperties = {
  position: 'absolute',
  zIndex: 7,
  maxWidth: 620,
  fontFamily: FONT_FAMILY,
  fontSize: 30,
  lineHeight: 1.35,
  fontWeight: 700,
  whiteSpace: 'pre-wrap',
  pointerEvents: 'none',
};

const VARIANTS: Record<LabelVariant, CSSProperties> = {
  pill: {
    padding: '10px 22px',
    borderRadius: 999,
    background: 'rgba(23,33,47,0.92)',
    border: '2px solid rgba(255,255,255,0.2)',
    color: '#ffffff',
    boxShadow: '0 8px 22px rgba(10,20,40,0.24)',
  },
  tag: {
    padding: '8px 16px',
    borderRadius: 8,
    background: '#fffdf7',
    border: '3px solid #2b2b2b',
    color: INK,
    boxShadow: '6px 6px 0 rgba(43,43,43,0.14)',
  },
  callout: {
    padding: '14px 22px',
    borderRadius: 18,
    background: 'rgba(255,253,247,0.97)',
    border: '3px solid #2b2b2b',
    color: INK,
    boxShadow: '0 14px 32px rgba(10,20,40,0.22)',
  },
  note: {
    padding: '12px 18px',
    borderRadius: 4,
    background: '#fff2b8',
    border: '2px solid #e0bd3f',
    color: '#3b3320',
    boxShadow: '8px 10px 0 rgba(120,90,20,0.16)',
  },
  badge: {
    padding: '8px 16px',
    borderRadius: 10,
    background: '#2f6fed',
    border: '2px solid rgba(255,255,255,0.35)',
    color: '#ffffff',
    fontSize: 28,
    boxShadow: '0 10px 24px rgba(47,111,237,0.32)',
  },
  stamp: {
    padding: '8px 18px',
    borderRadius: 6,
    background: 'rgba(255,255,255,0.08)',
    border: '3px dashed #c0392b',
    color: '#c0392b',
    letterSpacing: 3,
    textTransform: 'uppercase',
  },
};

export const Label = ({
  text,
  lines,
  left,
  top,
  variant = 'pill',
  rotate,
  opacity,
  maxWidth,
  fontSize,
  zIndex,
}: Props) => {
  const items = lines ?? (text ? [text] : []);

  return (
    <div
      style={{
        ...BASE,
        ...VARIANTS[variant],
        left,
        top,
        opacity,
        ...(maxWidth ? {maxWidth} : {}),
        ...(fontSize ? {fontSize} : {}),
        ...(zIndex ? {zIndex} : {}),
        ...(rotate ? {transform: `rotate(${rotate}deg)`} : {}),
      }}
    >
      {items.map((line, index) => (
        <div key={index}>{line}</div>
      ))}
    </div>
  );
};
