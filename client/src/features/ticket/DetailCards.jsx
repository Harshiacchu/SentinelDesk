import { Dot } from '../../components/ui/Tone.jsx';

/** Partial info at a glance; click any card for the full story. */
export function DetailCards({ details, onOpen }) {
  return (
    <section aria-label="Details" className="details-grid">
      {details.map((d, i) => (
        <button key={d.id} className="glass lift rise card-sm" onClick={() => onOpen(d.id)}
          style={{ textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 6, borderRadius: 18, padding: '18px 20px', animationDelay: `${0.3 + i * 0.06}s` }}>
          <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="eyebrow">{d.name}</span>
            <Dot tone={d.tone} glow />
          </span>
          <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.01em' }}>{d.partial}</span>
          <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.hint}</span>
          <span style={{ marginTop: 6, fontSize: 12, fontWeight: 600, color: 'var(--accent-text)' }}>View all →</span>
        </button>
      ))}
    </section>
  );
}
