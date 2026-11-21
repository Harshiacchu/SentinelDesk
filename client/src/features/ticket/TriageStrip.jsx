import { duration } from '../../lib/format.js';

const tone = (c) => (c >= 0.8 ? 'var(--green)' : c >= 0.6 ? 'var(--amber)' : 'var(--red)');

/** Type, queue and priority with their confidence, plus end-to-end latency, in one compact row. */
export function TriageStrip({ ticket }) {
  const t = ticket.triage;
  const total = ticket.latency.reduce((a, s) => a + s.ms, 0);
  const items = [['Type', t.type], ['Queue', t.queue], ['Priority', t.priority]];
  return (
    <div role="list" aria-label="Triage" style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'stretch' }}>
      {items.map(([name, p]) => {
        const pct = Math.round(p.confidence * 100);
        return (
          <div key={name} role="listitem" className="glass" title={`${name} confidence ${pct}%`}
            style={{ display: 'flex', flexDirection: 'column', gap: 5, padding: '7px 12px', borderRadius: 12, minWidth: 128, boxShadow: 'none' }}>
            <span style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 12 }}>
              <span className="faint">{name}</span>
              <strong style={{ fontSize: 13, textTransform: name === 'Priority' ? 'capitalize' : 'none' }}>{p.label}</strong>
              <span className="mono muted" style={{ marginLeft: 'auto', fontSize: 11 }}>{pct}%</span>
            </span>
            <span style={{ height: 3, borderRadius: 999, background: 'var(--hover)', overflow: 'hidden' }}>
              <span style={{ display: 'block', height: '100%', width: `${pct}%`, background: tone(p.confidence), borderRadius: 999 }} />
            </span>
          </div>
        );
      })}
      <div role="listitem" className="glass" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', borderRadius: 12, boxShadow: 'none', fontSize: 12 }}>
        <span className="faint">Triaged in</span><strong className="mono" style={{ fontSize: 13 }}>{duration(total)}</strong>
      </div>
    </div>
  );
}
