import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useTheme } from '../../theme/ThemeContext.jsx';
import { useReducedMotion } from '../../hooks/useReducedMotion.js';
import { tooltipStyle } from './ChartCard.jsx';

export function SeverityDonut({ severity }) {
  const { colors } = useTheme();
  const still = useReducedMotion();
  const data = [
    { name: 'Urgent (paged)', value: severity.critical ?? 0, color: colors.red },
    { name: 'Sent to an engineer', value: severity.review ?? 0, color: colors.amber },
    { name: 'Answered automatically', value: severity.ready ?? 0, color: colors.green },
  ];
  const total = data.reduce((a, d) => a + d.value, 0);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
      <div style={{ width: 170, height: 170, position: 'relative', flex: 'none' }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" innerRadius={56} outerRadius={78} paddingAngle={3} stroke="none" animationDuration={1100} isAnimationActive={!still}>
              {data.map((d) => <Cell key={d.name} fill={d.color} />)}
            </Pie>
            <Tooltip {...tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
          <span style={{ fontSize: 26, fontWeight: 800 }}>{total}</span><span className="muted" style={{ fontSize: 11 }}>tickets</span>
        </div>
      </div>
      <ul className="list" style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 13 }}>
        {data.map((d) => (
          <li key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="dot" style={{ background: d.color }} /> {d.name}
            <span className="mono muted" style={{ marginLeft: 8 }}>{total ? Math.round((d.value / total) * 100) : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
