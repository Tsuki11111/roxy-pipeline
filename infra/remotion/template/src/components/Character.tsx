import {Img, staticFile} from 'remotion';
import type {CSSProperties} from 'react';

const assetSrc = (value: string) =>
  value.startsWith('/') || value.startsWith('http') ? value : staticFile(value);

interface Props {
  src: string;
  side: 'left' | 'center' | 'right';
  height?: number;
  bottom?: number;
  offsetX?: number;
  opacity?: number;
  blur?: number;
  scale?: number;
  rotate?: number;
  zIndex?: number;
  style?: CSSProperties;
}

export const Character = ({
  src,
  side,
  height = 1000,
  bottom = 52,
  offsetX = 0,
  opacity = 1,
  blur = 0,
  scale = 1,
  rotate = 0,
  zIndex = 3,
  style,
}: Props) => {
  const left = side === 'left' ? 210 : side === 'right' ? 1120 : '50%';
  const translate =
    side === 'center'
      ? `translateX(calc(-50% + ${offsetX}px))`
      : `translateX(${offsetX}px)`;

  return (
    <Img
      src={assetSrc(src)}
      style={{
        position: 'absolute',
        left,
        bottom,
        height,
        width: 'auto',
        opacity,
        transform: `${translate} scale(${scale}) rotate(${rotate}deg)`,
        transformOrigin: 'bottom center',
        filter: `drop-shadow(0 10px 10px rgba(43, 43, 43, 0.22)) blur(${Math.max(
          0,
          blur,
        )}px)`,
        willChange: 'transform, opacity, filter',
        ...style,
        // 角色固定在内容下方；Stage 的 isolation 保证它仍在舞台背景之上。
        zIndex: Math.min(zIndex, -1),
      }}
    />
  );
};
