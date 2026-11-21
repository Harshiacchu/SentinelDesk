import { useEffect, useState } from 'react';
import { TicketComposer } from './TicketComposer.jsx';

/** ⌘K quick-triage overlay. */
export function CommandPalette({ open, onClose, onTriage }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return undefined;
    setError(null);
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  const submit = async (form) => {
    setBusy(true);
    setError(null);
    try { await onTriage(form); onClose(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  return (
    <div className="scrim fade" style={{ justifyContent: 'center', alignItems: 'flex-start', paddingTop: '12vh' }} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section role="dialog" aria-modal="true" aria-label="New ticket" className="glass-strong pop" style={{ width: 660, maxWidth: 'calc(100% - 32px)', borderRadius: 20, padding: 22, boxShadow: '0 30px 80px rgba(0,0,0,0.45)' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>New problem</strong>
          <span className="kbd" style={{ marginLeft: 'auto' }}>esc</span>
        </div>
        <TicketComposer onSubmit={submit} busy={busy} error={error} autoFocus compact />
      </section>
    </div>
  );
}
