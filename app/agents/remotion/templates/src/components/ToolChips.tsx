import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ACCENT} from '../theme';

const TOOLS = [
  {icon: '🔎', label: '搜索'},
  {icon: '🌐', label: '浏览器'},
  {icon: '💻', label: '代码'},
  {icon: '📄', label: '文件'},
];

interface Props {
  start?: number;
  top?: number;
  left?: number;
}

export const ToolChips = ({start = 0, top = 650, left = 460}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        display: 'flex',
        gap: 18,
        zIndex: 4,
      }}
    >
      {TOOLS.map((tool, index) => {
        const pop = spring({
          frame: Math.max(0, frame - start - index * 8),
          fps,
          config: {damping: 11, stiffness: 150, mass: 0.6},
        });
        return (
          <div
            key={tool.label}
            style={{
              padding: '14px 22px',
              borderRadius: 999,
              background: '#fffdf7',
              border: `3px solid ${ACCENT}`,
              boxShadow: '0 8px 0 rgba(109, 93, 252, 0.12)',
              fontSize: 28,
              fontWeight: 700,
              opacity: Math.min(1, pop),
              transform: `translateY(${(1 - pop) * 30}px) scale(${0.9 + 0.1 * pop})`,
            }}
          >
            <span style={{marginRight: 8}}>{tool.icon}</span>
            {tool.label}
          </div>
        );
      })}
    </div>
  );
};
