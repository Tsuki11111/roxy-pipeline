import {AbsoluteFill, Img, staticFile} from 'remotion';
import {FONT_FAMILY, INK, PAPER} from '../theme';

const assetSrc = (value: string) =>
  value.startsWith('/') || value.startsWith('http') ? value : staticFile(value);

interface Props {
  children: React.ReactNode;
  bg?: string;
  floor?: string;
}

export const Stage = ({
  children,
  bg = 'assets/background.png',
  floor = 'assets/floor.png',
}: Props) => (
  <AbsoluteFill
    style={{
      backgroundColor: PAPER,
      color: INK,
      fontFamily: FONT_FAMILY,
      overflow: 'hidden',
    }}
  >
    <Img
      src={assetSrc(bg)}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        objectFit: 'cover',
      }}
    />
    <Img
      src={assetSrc(floor)}
      style={{
        position: 'absolute',
        left: 0,
        bottom: 52,
        width: '100%',
        height: 300,
        objectFit: 'cover',
        WebkitMaskImage:
          'linear-gradient(to bottom, transparent 0%, #000 18%)',
      }}
    />
    {children}
  </AbsoluteFill>
);
