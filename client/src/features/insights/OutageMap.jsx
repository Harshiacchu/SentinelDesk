/**
 * Location map: each office is a point on a stylised regional panel.
 * Circle size + colour grow with live incident count; outage-level sites pulse.
 * Simple equirectangular projection per region box: no map tiles, no extra library.
 */
const REGIONS = {
  'North America': { lon: [-95, -62], lat: [36, 47] },
  Europe: { lon: [-6, 22], lat: [46, 56] },
};

const project = (site, box, w, h) => ({
  x: ((site.lon - box.lon[0]) / (box.lon[1] - box.lon[0])) * w,
  y: (1 - (site.lat - box.lat[0]) / (box.lat[1] - box.lat[0])) * h,
});

export function OutageMap({ sites }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
      {Object.entries(REGIONS).map(([region, box]) => (
        <RegionPanel key={region} region={region} box={box} sites={sites.filter((s) => s.region === region)} />
      ))}
    </div>
  );
}

function RegionPanel({ region, box, sites }) {
  const W = 360;
  const H = 220;
  const hot = sites.filter((s) => s.hot).length;
  const id = region.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return (
    <figure style={{ margin: 0, borderRadius: 16, border: '1px solid var(--border)', background: 'var(--glass-soft)', padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <figcaption style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <strong style={{ fontSize: 13 }}>{region}</strong>
        <span className="muted" style={{ fontSize: 12 }}>{hot ? `${hot} site${hot > 1 ? 's' : ''} at outage level` : 'no outages'}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${region} outage map`} style={{ width: '100%', height: 'auto' }}>
        <defs>
          <pattern id={`dots-${id}`} width="12" height="12" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.2" fill="var(--grid-dot)" /></pattern>
          <radialGradient id={`heat-${id}`}><stop offset="0%" stopColor="var(--red)" stopOpacity="0.55" /><stop offset="100%" stopColor="var(--red)" stopOpacity="0" /></radialGradient>
        </defs>
        <rect width={W} height={H} rx="12" fill={`url(#dots-${id})`} />
        {sites.map((s) => {
          const { x, y } = project(s, box, W - 40, H - 40);
          const cx = x + 20;
          const cy = y + 20;
          // Put the label on the left when a neighbour sits just to the right (avoids overlap).
          const crowded = sites.some((o) => {
            if (o === s) return false;
            const p = project(o, box, W - 40, H - 40);
            return p.x > x && p.x - x < 110 && Math.abs(p.y - y) < 26;
          });
          const lx = crowded ? cx - 10 : cx + 10;
          const anchor = crowded ? 'end' : 'start';
          const r = 6 + Math.min(26, s.incidents * 4);
          const tone = s.hot ? 'var(--red)' : s.incidents ? 'var(--amber)' : 'var(--green)';
          return (
            <g key={s.name}>
              {s.incidents > 0 && <circle cx={cx} cy={cy} r={r * 1.8} fill={`url(#heat-${id})`} opacity={s.hot ? 1 : 0.5} />}
              {s.hot && (
                <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--red)" strokeWidth="2">
                  <animate attributeName="r" from={r} to={r * 2.2} dur="1.8s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.8" to="0" dur="1.8s" repeatCount="indefinite" />
                </circle>
              )}
              <circle cx={cx} cy={cy} r={s.incidents ? 6 : 4} fill={tone} style={{ filter: `drop-shadow(0 0 6px ${tone})` }} />
              <text x={lx} y={cy - 8} textAnchor={anchor} fontSize="11" fontWeight="600" fill="var(--text)">{s.name}</text>
              <text x={lx} y={cy + 6} textAnchor={anchor} fontSize="10" fill="var(--muted)">
                {s.incidents ? `${s.incidents} incident${s.incidents > 1 ? 's' : ''}${s.top ? ` · ${s.top.topic}` : ''}` : 'clear'}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
