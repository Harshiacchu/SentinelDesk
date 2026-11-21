import { reasonInfo } from '../../lib/severity.js';
import { clock } from '../../lib/format.js';

const pretty = (label, value) => (label.endsWith('reasons') && value !== '—'
  ? value.split(', ').map((c) => reasonInfo(c).title).join(', ')
  : value);

/** After a follow-up: what the re-triage changed, so nobody has to diff it by eye. */
export function ChangeBanner({ lastChange }) {
  if (!lastChange) return null;
  const { changes, at } = lastChange;
  return (
    <section aria-label="What changed" className="glass rise tone-info" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 16px', borderRadius: 14, borderColor: 'color-mix(in srgb, var(--accent) 35%, transparent)' }}>
      <strong style={{ fontSize: 13 }}>Re-triaged after a follow-up · {clock(at)}</strong>
      {changes.length === 0
        ? <span className="muted" style={{ fontSize: 13 }}>The new information didn’t change the decision.</span>
        : (
          <ul className="list" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 18px', fontSize: 13 }}>
            {changes.map((c) => (
              <li key={c.label}>
                <span className="muted">{c.label}:</span>{' '}
                {c.from !== '—' && <span style={{ textDecoration: 'line-through', color: 'var(--muted)' }}>{pretty(c.label, c.from)}</span>}
                {c.from !== '—' && c.to !== '—' && ' → '}
                {c.to !== '—' && <strong>{pretty(c.label, c.to)}</strong>}
              </li>
            ))}
          </ul>
        )}
    </section>
  );
}
