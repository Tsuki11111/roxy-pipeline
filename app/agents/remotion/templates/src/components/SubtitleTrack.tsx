import {useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT_FAMILY} from '../theme';

export interface SubtitleChunk {
  text: string;
  start_ms: number;
  end_ms: number;
}

interface Props {
  chunks: SubtitleChunk[];
  bottom?: number;
}

export const SubtitleTrack = ({chunks, bottom = 40}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const timeMs = (frame / fps) * 1000;
  const chunk = chunks.find(
    (item) => timeMs >= item.start_ms && timeMs < item.end_ms,
  );
  if (!chunk) {
    return null;
  }

  return (
    <div
      style={{
        position: 'absolute',
        left: '50%',
        bottom,
        transform: 'translateX(-50%)',
        maxWidth: 1500,
        padding: '14px 30px',
        background: 'rgba(30,30,35,0.88)',
        color: '#ffffff',
        borderRadius: 14,
        fontSize: 38,
        lineHeight: 1.4,
        textAlign: 'center',
        whiteSpace: 'nowrap',
        fontFamily: FONT_FAMILY,
        zIndex: 100,
        pointerEvents: 'none',
      }}
    >
      {chunk.text}
    </div>
  );
};
