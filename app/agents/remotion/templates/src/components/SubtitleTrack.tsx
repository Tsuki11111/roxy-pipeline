import {useCurrentFrame, useVideoConfig} from 'remotion';
import {CLAY, FONT_FAMILY, INK, PAPER_LIGHT} from '../theme';

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
        padding: '13px 28px 13px 30px',
        background: 'rgba(250,246,237,0.94)',
        color: INK,
        border: '1px solid rgba(35,32,27,0.24)',
        borderLeft: `4px solid ${CLAY}`,
        borderRadius: '5px 13px 7px 11px',
        boxShadow: '5px 7px 0 rgba(35,32,27,0.06)',
        fontSize: 34,
        lineHeight: 1.45,
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
