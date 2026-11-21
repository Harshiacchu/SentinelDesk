/**
 * Apple-Fitness-style concentric rings. Each ring: { value 0..1+, color }.
 * Values above 1 render as a full ring (the label carries the "3x" detail).
 */
export function ActivityRings({ rings, size = 132, stroke = 12, trackOpacity = 0.16, label }) {
  const c = size / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
      {rings.map((ring, i) => {
        const r = c - stroke / 2 - i * (stroke + 3);
        const len = 2 * Math.PI * r;
        const off = len * (1 - Math.min(ring.value, 0.999));
        return (
          <g key={i}>
            <circle cx={c} cy={c} r={r} fill="none" stroke={ring.color} strokeOpacity={trackOpacity} strokeWidth={stroke} />
            <circle
              className="ring-draw"
              cx={c} cy={c} r={r} fill="none" stroke={ring.color} strokeWidth={stroke} strokeLinecap="round"
              strokeDasharray={`${len} ${len}`} transform={`rotate(-90 ${c} ${c})`}
              style={{ '--len': len, strokeDashoffset: off, filter: `drop-shadow(0 0 6px ${ring.color}99)` }}
            />
          </g>
        );
      })}
    </svg>
  );
}
