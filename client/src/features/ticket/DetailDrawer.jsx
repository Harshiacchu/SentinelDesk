import { useState } from 'react';
import { Drawer } from '../../components/ui/Drawer.jsx';
import { ConfidenceBar, Dot } from '../../components/ui/Tone.jsx';

/** Full detail for every card, switchable by tabs without closing. */
export function DetailDrawer({ ticket, details, openId, onSelect, onClose, onAddNote }) {
  const detail = details.find((d) => d.id === openId);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    if (!note.trim()) return;
    setSaving(true);
    try { await onAddNote(note.trim()); setNote(''); } finally { setSaving(false); }
  };

  return (
    <Drawer open={Boolean(detail)} onClose={onClose} eyebrow={ticket.subject || ticket.ticketId} title={detail?.name ?? ''}>
      <div role="tablist" aria-label="Detail sections" className="tabs" style={{ padding: '0 24px' }}>
        {details.map((d) => (
          <button key={d.id} role="tab" className="tab" aria-selected={d.id === openId} onClick={() => onSelect(d.id)}>{d.name}</button>
        ))}
      </div>

      {detail?.id === 'activity' && (
        <form onSubmit={save} style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '16px 24px 0' }}>
          <label htmlFor="note" className="muted" style={{ fontSize: 12 }}>Note for the next shift</label>
          <textarea id="note" className="field" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Gateway cert renewed at 10:05, waiting on confirmation" style={{ resize: 'none' }} />
          <button className="btn btn-accent press" disabled={saving || !note.trim()} style={{ alignSelf: 'flex-end' }}>{saving ? 'Saving…' : 'Add note'}</button>
        </form>
      )}

      <ul className="list scroll" style={{ padding: '6px 24px 24px', flex: 1 }}>
        {detail?.rows.map((r, i) => (
          <li key={r.key} className="row rise" style={{ animationDelay: `${i * 0.04}s` }}>
            <Dot tone={r.tone} glow />
            <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{r.title}</span>
              <span className="muted" style={{ fontSize: 13, lineHeight: 1.5 }}>{r.text}</span>
              {r.bar !== undefined && <ConfidenceBar value={r.bar} />}
            </span>
            {r.meta && <span className="mono" style={{ fontSize: 12, color: 'var(--text-2)', flex: 'none' }}>{r.meta}</span>}
          </li>
        ))}
      </ul>
    </Drawer>
  );
}
