import { useEffect, useState } from 'react';
import { SEVERITY, STATUS_LABEL } from '../../lib/severity.js';
import { toneClass } from '../../components/ui/Tone.jsx';

const SECONDARY = {
  critical: [['send', 'Send holding update'], ['resolve', 'Mark resolved']],
  review: [['send', 'Send safe version only'], ['resolve', 'Close without reply']],
  ready: [['handoff', 'Hand to a person instead'], ['resolve', 'Close without reply']],
};

/** One obvious next step per ticket; everything else tucked under "More". */
export function ActionCard({ ticket, onAction, busy }) {
  const [more, setMore] = useState(false);
  const [undoUntil, setUndoUntil] = useState(0);
  const sev = SEVERITY[ticket.severity];
  const done = ticket.status !== 'open';

  useEffect(() => {
    if (!undoUntil) return undefined;
    const t = setTimeout(() => setUndoUntil(0), Math.max(0, undoUntil - Date.now()));
    return () => clearTimeout(t);
  }, [undoUntil]);

  const run = async (action) => {
    await onAction(action);
    if (action === 'send') setUndoUntil(Date.now() + 5000);
  };

  return (
    <section className={`glass card rise ${toneClass(ticket.severity)}`} style={{ padding: 20, gap: 12, animationDelay: '.2s' }}>
      {done ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 15, fontWeight: 700 }}>{STATUS_LABEL[ticket.status]}</span>
          {undoUntil > Date.now()
            ? <button className="btn-link" onClick={() => onAction('reopen')}>Undo</button>
            : <button className="btn-link" onClick={() => onAction('reopen')} style={{ marginLeft: 'auto' }}>Reopen</button>}
        </div>
      ) : (
        <button className="btn btn-primary press" disabled={busy} onClick={() => run(sev.primary.action)}>
          {busy ? 'Working…' : sev.primary.label}
        </button>
      )}

      <span style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 13 }}>
        <button className="btn-link" onClick={() => navigator.clipboard?.writeText(ticket.draft?.lines.filter((l) => !l.unsupported).map((l) => l.text).join('') ?? '')}>Copy draft</button>
        <button className="btn-link" style={{ marginLeft: 'auto', color: 'var(--muted)' }} aria-expanded={more} onClick={() => setMore((v) => !v)}>
          {more ? 'Less ▴' : 'More ▾'}
        </button>
      </span>

      {more && (
        <div className="fade" style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
          {SECONDARY[ticket.severity].map(([action, label]) => (
            <button key={action} className="btn row-hover" style={{ justifyContent: 'flex-start', fontWeight: 500 }} disabled={busy || done} onClick={() => run(action)}>{label}</button>
          ))}
        </div>
      )}
      <span className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>{sev.lock}</span>
    </section>
  );
}
