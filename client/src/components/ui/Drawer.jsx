import { useEffect } from 'react';
import { Icon } from './Icon.jsx';

/** Right-side sheet. Closes on Escape or backdrop click. */
export function Drawer({ open, onClose, eyebrow, title, children, width = 460 }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="scrim fade" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section role="dialog" aria-modal="true" aria-label={title} className="drawer glass-strong slide-in" style={{ width }}>
        <div className="drawer-head">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, letterSpacing: '-0.02em' }}>{title}</h2>
          </div>
          <button className="icon-btn press" onClick={onClose} aria-label="Close" style={{ marginLeft: 'auto' }}><Icon name="close" /></button>
        </div>
        {children}
      </section>
    </div>
  );
}
