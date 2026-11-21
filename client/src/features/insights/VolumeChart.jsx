import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useTheme } from '../../theme/ThemeContext.jsx';
import { useReducedMotion } from '../../hooks/useReducedMotion.js';
import { clock } from '../../lib/format.js';
import { tooltipStyle } from './ChartCard.jsx';

export function VolumeChart({ volume }) {
  const { colors } = useTheme();
  const still = useReducedMotion();
  const data = volume.map((b) => ({ ...b, time: clock(b.start) }));
  const series = [['critical', 'Critical', colors.red], ['review', 'Needs a person', colors.amber], ['ready', 'Auto-drafted', colors.green]];
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            {series.map(([key, , c]) => (
              <linearGradient key={key} id={`g-${key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c} stopOpacity={0.5} /><stop offset="100%" stopColor={c} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke={colors.grid} vertical={false} />
          <XAxis dataKey="time" tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={24} />
          <YAxis tick={{ fill: colors.muted, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
          <Tooltip {...tooltipStyle} />
          {[...series].reverse().map(([key, name, c]) => (
            <Area key={key} type="monotone" dataKey={key} name={name} stackId="1" stroke={c} strokeWidth={2} fill={`url(#g-${key})`} animationDuration={1200} isAnimationActive={!still} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
