import {Img, staticFile} from 'remotion';

const assetSrc = (value: string) =>
  value.startsWith('/') || value.startsWith('http') ? value : staticFile(value);

interface Props {
  src: string;
  width?: number;
  bottom?: number;
  offsetY?: number;
  scale?: number;
  opacity?: number;
}

export const Overlay = ({
  src,
  width = 420,
  bottom = 120,
  offsetY = 0,
  scale = 1,
  opacity = 1,
}: Props) => (
  <Img
    src={assetSrc(src)}
    style={{
      position: 'absolute',
      left: '50%',
      bottom,
      width,
      height: 'auto',
      zIndex: 2,
      opacity,
      transform: `translateX(-50%) translateY(${offsetY}px) scale(${scale})`,
      mixBlendMode: 'multiply',
    }}
  />
);
