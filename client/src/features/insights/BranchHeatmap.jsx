import { useState } from 'react';

/**
 * Branch x topic grid. Cell colour = how many incidents of that kind a site has right now.
 * Pulsing cells have reached the outage level.
 */
export function BranchHeatmap({ data }) {
  const [hover, setHover] = useState(null);
  const value = (b, t) => data.cells.find((c) => c.branch === b && c.topic === t);
  const cols = `120px repeat(${data.topics.length}, minmax(44px, 1fr))`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflowX: 'auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 6, minWidth: 520 }}>
        <span />
        {data.topics.map((t) => <span key={t} className="faint" style={{ fontSize: 11, fontWeight: 600, textAlign: 'center' }}>{t}</span>)}
        {data.branches.map((b) => (
          <Row key={b} branch={b} topics={data.topics} value={value} max={data.max} onHover={setHover} />
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12 }} className="muted">
        <span>0</span>
        <span style={{ width: 140, height: 8, borderRadius: 999, background: 'linear-gradient(90deg, var(--hover), color-mix(in srgb, var(--red) 90%, transparent))' }} />
        <span>{data.max}+</span>
        <span style={{ marginLeft: 'auto' }}>{hover ? `${hover.branch} · ${hover.topic}: ${hover.value} incident${hover.value === 1 ? '' : 's'}` : `Pulsing = ${data.hotThreshold}+ similar incidents (outage level)`}</span>
      </div>
    </div>
  );
}

function Row({ branch, topics, value, max, onHover }) {
  return (
    <>
      <span style={{ fontSize: 13, fontWeight: 500, alignSelf: 'center' }}>{branch}</span>
      {topics.map((t) => {
        const cell = value(branch, t);
        const v = cell?.value ?? 0;
        const mix = v === 0 ? 0 : 18 + Math.round((v / max) * 72);
        return (
          <button key={t} className={`press ${cell?.hot ? 'heat-hot' : ''}`} onMouseEnter={() => onHover(cell)} onMouseLeave={() => onHover(null)} onFocus={() => onHover(cell)}
            aria-label={`${branch}, ${t}: ${v} incidents`}
            style={{ height: 36, borderRadius: 9, border: '1px solid var(--border)', fontSize: 12, fontWeight: 700, color: mix > 55 ? '#fff' : 'var(--text-2)',
              background: v ? `color-mix(in srgb, var(--red) ${mix}%, transparent)` : 'var(--glass-soft)' }}>
            {v || ''}
          </button>
        );
      })}
    </>
  );
}
