import {INK} from '../theme';

export type CardKind =
  | 'chat'
  | 'chat_bubble'
  | 'pure'
  | 'pure_text'
  | 'terminal'
  | 'browser'
  | 'icon';

interface Props {
  kind: CardKind;
  text?: string;
  side?: 'left' | 'right';
  opacity?: number;
  translateY?: number;
  scale?: number;
  zIndex?: number;
  full?: boolean;
  lines?: string[];
  reveal?: number;
  top?: number;
  width?: number;
}

const chatTail = (side: 'left' | 'right'): React.CSSProperties =>
  side === 'right'
    ? {
        position: 'absolute',
        left: -22,
        top: 64,
        width: 34,
        height: 34,
        background: '#fffdf7',
        borderLeft: '3px solid #2b2b2b',
        borderBottom: '3px solid #2b2b2b',
        transform: 'rotate(45deg)',
      }
    : {
        position: 'absolute',
        right: -22,
        top: 64,
        width: 34,
        height: 34,
        background: '#fffdf7',
        borderRight: '3px solid #2b2b2b',
        borderTop: '3px solid #2b2b2b',
        transform: 'rotate(45deg)',
      };

export const Card = ({
  kind,
  text = '',
  side = 'right',
  opacity = 1,
  translateY = 0,
  scale = 1,
  zIndex = 4,
  full = true,
  lines,
  reveal,
  top = 150,
  width = 820,
}: Props) => {
  const normalized = kind === 'chat_bubble' ? 'chat' : kind === 'pure_text' ? 'pure' : kind;
  if (normalized === 'pure') {
    const position: React.CSSProperties =
      side === 'right' ? {right: 80} : {left: 80};
    return (
      <div
        style={{
          position: 'absolute',
          ...(full ? {left: '50%', top: 250, width: 1400} : {top, width, ...position}),
          zIndex,
          opacity,
          transform: full
            ? `translateX(-50%) translateY(${translateY}px) scale(${scale})`
            : `translateY(${translateY}px) scale(${scale})`,
          textAlign: 'center',
          fontSize: full ? 76 : 54,
          fontWeight: 700,
          lineHeight: 1.35,
          whiteSpace: 'pre-wrap',
          color: INK,
        }}
      >
        {text}
      </div>
    );
  }

  if (normalized === 'icon') {
    return (
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '38%',
          zIndex,
          opacity,
          transform: `translateX(-50%) translateY(${translateY}px) scale(${scale})`,
          fontSize: 160,
          lineHeight: 1.2,
          textAlign: 'center',
        }}
      >
        {text}
      </div>
    );
  }

  const position: React.CSSProperties =
    side === 'right' ? {right: 80} : {left: 80};
  const visibleLines = reveal ?? lines?.length ?? 0;
  const body: React.ReactNode = lines ? (
    <div>
      {lines.map((line, index) => (
        <div
          key={`${line}-${index}`}
          style={{
            opacity: index < visibleLines ? 1 : 0.16,
            transform: `translateY(${index < visibleLines ? 0 : 8}px)`,
          }}
        >
          {line}
        </div>
      ))}
    </div>
  ) : (
    text
  );

  return (
    <div
      style={{
        position: 'absolute',
        top,
        width,
        zIndex,
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        transformOrigin: side === 'right' ? 'top right' : 'top left',
        ...position,
      }}
    >
      {normalized === 'chat' && (
        <div
          style={{
            position: 'relative',
            padding: '34px 38px',
            background: '#fffdf7',
            border: '3px solid #2b2b2b',
            borderRadius: 20,
            boxShadow: '10px 10px 0 rgba(43, 43, 43, 0.16)',
            fontSize: 36,
            lineHeight: 1.55,
            whiteSpace: 'pre-wrap',
          }}
        >
          <div style={chatTail(side)} />
          <span
            style={{
              display: 'inline-block',
              marginBottom: 14,
              padding: '2px 14px',
              background: '#2b2b2b',
              color: '#fff',
              borderRadius: 999,
              fontSize: 20,
              lineHeight: 1.6,
            }}
          >
            AI
          </span>
          <div>{body}</div>
        </div>
      )}

      {normalized === 'terminal' && (
        <div
          style={{
            overflow: 'hidden',
            background: '#1e1e2e',
            border: '3px solid #11111b',
            borderRadius: 16,
            boxShadow: '10px 10px 0 rgba(0, 0, 0, 0.24)',
            color: '#cdd6f4',
            fontFamily: 'Consolas, "Courier New", monospace',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              height: 46,
              padding: '0 18px',
              background: '#181825',
            }}
          >
            <Dot color="#f38ba8" />
            <Dot color="#f9e2af" />
            <Dot color="#a6e3a1" />
          </div>
          <div
            style={{
              padding: '28px 32px',
              fontSize: 30,
              lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
            }}
          >
            {body}
          </div>
        </div>
      )}

      {normalized === 'browser' && (
        <div
          style={{
            overflow: 'hidden',
            background: '#fff',
            border: '3px solid #2b2b2b',
            borderRadius: 16,
            boxShadow: '10px 10px 0 rgba(43, 43, 43, 0.16)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              height: 46,
              padding: '0 18px',
              background: '#ece7dc',
              borderBottom: '3px solid #2b2b2b',
            }}
          >
            <Dot color="#f38ba8" />
            <Dot color="#f9e2af" />
            <Dot color="#a6e3a1" />
          </div>
          <div
            style={{
              padding: '28px 32px',
              fontSize: 34,
              lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
            }}
          >
            {body}
          </div>
        </div>
      )}
    </div>
  );
};

const Dot = ({color}: {color: string}) => (
  <span
    style={{
      width: 14,
      height: 14,
      borderRadius: '50%',
      background: color,
    }}
  />
);
