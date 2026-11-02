import {Img, staticFile} from 'remotion';
import type {CSSProperties} from 'react';
import {createPortal} from 'react-dom';
import {useCharacterLayer} from './Stage';

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

  const layer = useCharacterLayer();
  const image = (
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
        // 角色永远在卡片下方，避免生成代码用 style/zIndex 把卡片文字盖住。
        zIndex: Math.min(zIndex, Number(style?.zIndex) || zIndex, 5),
      }}
    />
  );
  // 角色统一进 Stage 的背景层，SVG 图示、卡片等所有内容层永远在它上方。
  return layer ? createPortal(image, layer) : image;
};
