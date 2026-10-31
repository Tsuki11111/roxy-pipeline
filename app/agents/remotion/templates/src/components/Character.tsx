import {Img, staticFile} from 'remotion';

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
        zIndex,
        opacity,
        transform: `${translate} scale(${scale}) rotate(${rotate}deg)`,
        transformOrigin: 'bottom center',
        filter: `drop-shadow(0 10px 10px rgba(43, 43, 43, 0.22)) blur(${Math.max(
          0,
          blur,
        )}px)`,
        willChange: 'transform, opacity, filter',
      }}
    />
  );
};
