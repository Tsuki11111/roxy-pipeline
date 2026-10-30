interface Props {
  text: string;
  opacity?: number;
}

export const Subtitle = ({text, opacity = 1}: Props) => (
  <div
    style={{
      position: 'absolute',
      left: '50%',
      bottom: 104,
      transform: 'translateX(-50%)',
      maxWidth: 1500,
      padding: '14px 30px',
      background: 'rgba(30, 30, 35, 0.88)',
      color: '#fff',
      borderRadius: 14,
      fontSize: 38,
      lineHeight: 1.4,
      textAlign: 'center',
      whiteSpace: 'nowrap',
      zIndex: 6,
      opacity,
    }}
  >
    {text}
  </div>
);
