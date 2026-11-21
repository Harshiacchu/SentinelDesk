import { useState } from 'react';
import { clock } from '../../lib/format.js';

/**
 * Problem type x hour. Each cell = how many incidents of that kind came in that hour.
 * Pulsing cells are hours where one problem hit the outage level.
 */
export function ProblemHeatmap({ data }) {
  const [hover, setHover] = useState(null);
  const cols = `110px repeat(${data.hours.length}, minmax(52px, 1fr))`;
  const cell = (topic, slot) => data.cells.find((c) => c.topic === topic && c.slot === slot);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflowX: 'auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 6, minWidth: 480 }}>
        <span />
        {data.hours.map((h) => <span key={h} className="faint" style={{ fontSize: 11, fontWeight: 600, textAlign: 'center' }}>{clock(h)}</span>)}
        {data.topics.map((topic) => (
          <Row key={topic} topic={topic} slots={data.hours.length} cell={cell} max={data.max} onHover={setHover} hours={data.hours} />
        ))}
      </div>
      <div className="muted" style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, flexWrap: 'wrap' }}>
        <span>0</span>
        <span style={{ width: 120, height: 8, borderRadius: 999, background: 'linear-gradient(90deg, var(--hover), color-mix(in srgb, var(--red) 90%, transparent))' }} />
        <span>{data.max}</span>
        <span style={{ marginLeft: 'auto' }}>
          {hover ? `${hover.topic} at ${clock(hover.hour)}: ${hover.value} incident${hover.value === 1 ? '' : 's'}` : `Pulsing = ${data.hotThreshold}+ of the same problem in one hour, probably an outage`}
        </span>
      </div>
    </div>
  );
}

function Row({ topic, slots, cell, max, onHover, hours }) {
  return (
    <>
      <span style={{ fontSize: 13, fontWeight: 500, alignSelf: 'center' }}>{topic}</span>
      {Array.from({ length: slots }, (_, slot) => {
        const c = cell(topic, slot);
        const v = c?.value ?? 0;
        const mix = v === 0 ? 0 : 15 + Math.round((v / max) * 75);
        return (
          <button key={slot} className={`press ${c?.hot ? 'heat-hot' : ''}`} aria-label={`${topic} at ${clock(hours[slot])}: ${v} incidents`}
            onMouseEnter={() => onHover({ topic, value: v, hour: hours[slot] })} onMouseLeave={() => onHover(null)} onFocus={() => onHover({ topic, value: v, hour: hours[slot] })}
            style={{ height: 34, borderRadius: 9, border: '1px solid var(--border)', fontSize: 12, fontWeight: 700, color: mix > 55 ? '#fff' : 'var(--text-2)',
              background: v ? `color-mix(in srgb, var(--red) ${mix}%, transparent)` : 'var(--glass-soft)' }}>
            {v || ''}
          </button>
        );
      })}
    </>
  );
}
