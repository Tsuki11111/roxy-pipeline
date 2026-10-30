interface Props {
  lines: string[] | string;
  side?: 'left' | 'right' | 'center';
  bottom?: number;
  maxWidth?: number;
  opacity?: number;
}

export const Caption = ({
  lines,
  side = 'left',
  bottom = 120,
  maxWidth = 760,
  opacity = 1,
}: Props) => {
  const items = Array.isArray(lines) ? lines : [lines];
  const horizontal =
    side === 'center'
      ? {left: '50%', transform: 'translateX(-50%)'}
      : side === 'left'
        ? {left: 80}
        : {right: 80};

  return (
    <div
      style={{
        position: 'absolute',
        bottom,
        ...horizontal,
        maxWidth,
        zIndex: 6,
        opacity,
        pointerEvents: 'none',
        padding: '14px 26px',
        borderRadius: 14,
        background: 'rgba(18,22,32,0.86)',
        border: '2px solid rgba(255,255,255,0.18)',
        color: '#ffffff',
        fontSize: 32,
        lineHeight: 1.5,
        textAlign: side === 'center' ? 'center' : 'left',
      }}
    >
      {items.map((line, index) => (
        <div key={index}>{line}</div>
      ))}
    </div>
  );
};
