import {AbsoluteFill} from 'remotion';
import {FONT_FAMILY, INK, PAPER} from '../theme';

interface Props {
  children: React.ReactNode;
  bg?: string;
  floor?: string;
}

export const Stage = ({children}: Props) => (
  <AbsoluteFill
    style={{
      backgroundColor: PAPER,
      color: INK,
      fontFamily: FONT_FAMILY,
      overflow: 'hidden',
    }}
  >
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background:
          'radial-gradient(circle at 16% 12%, rgba(191,91,59,0.055), transparent 30%), radial-gradient(circle at 86% 84%, rgba(119,133,111,0.07), transparent 32%)',
      }}
    />
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundImage:
          'radial-gradient(rgba(35,32,27,0.045) 0.7px, transparent 0.7px)',
        backgroundSize: '6px 6px',
        opacity: 0.55,
      }}
    />
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        height: 230,
        background:
          'linear-gradient(to bottom, rgba(35,32,27,0), rgba(35,32,27,0.07))',
      }}
    />
    <div
      style={{
        position: 'absolute',
        left: 70,
        right: 70,
        bottom: 196,
        height: 1,
        background: 'rgba(35,32,27,0.16)',
      }}
    />
    <svg
      viewBox="0 0 32 32"
      fill="none"
      style={{
        position: 'absolute',
        right: 62,
        top: 52,
        width: 118,
        height: 118,
        color: '#bf5b3b',
        opacity: 0.1,
      }}
    >
      <path
        d="M16 2v28M2 16h28M7 7l18 18M25 7 7 25"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
    {children}
  </AbsoluteFill>
);
