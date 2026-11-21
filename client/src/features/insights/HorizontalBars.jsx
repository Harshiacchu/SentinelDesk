import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useTheme } from '../../theme/ThemeContext.jsx';
import { useReducedMotion } from '../../hooks/useReducedMotion.js';
import { tooltipStyle } from './ChartCard.jsx';

/** Generic ranked bar chart (queues, gate reasons…). */
export function HorizontalBars({ data, labelKey = 'name', valueKey = 'value', colorFor }) {
  const { colors } = useTheme();
  const still = useReducedMotion();
  const height = Math.max(160, data.length * 34);
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis type="category" dataKey={labelKey} width={150} tick={{ fill: colors.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey={valueKey} radius={[0, 8, 8, 0]} barSize={16} animationDuration={1000} isAnimationActive={!still}>
            {data.map((d) => <Cell key={d[labelKey]} fill={colorFor ? colorFor(d, colors) : colors.blue} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
