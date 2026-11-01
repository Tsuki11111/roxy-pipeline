interface Props {
  labels: string[];
  active: number;
}

export const Progress = ({labels, active}: Props) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      right: 0,
      bottom: 0,
      height: 52,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-around',
      background: 'rgba(30, 30, 35, 0.94)',
      zIndex: 7,
    }}
  >
    {labels.map((label, index) => (
      <div
        key={label}
        style={{
          position: 'relative',
          color: index === active ? '#fff' : '#8f949c',
          fontSize: 20,
          letterSpacing: '0.04em',
          fontWeight: index === active ? 700 : 400,
        }}
      >
        {label}
        {index === active && (
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: -14,
              height: 3,
              background: '#fff',
            }}
          />
        )}
      </div>
    ))}
  </div>
);
