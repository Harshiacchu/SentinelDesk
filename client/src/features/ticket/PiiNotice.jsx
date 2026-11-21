import { useState } from 'react';
import { Icon } from '../../components/ui/Icon.jsx';

const LABELS = { EMAIL: 'email', PHONE: 'phone number', IP: 'IP address', IBAN: 'IBAN', CARD: 'card number', ACCOUNT: 'account number' };
const describe = (entities) => entities.map(({ type, count }) => `${count} ${LABELS[type] ?? type.toLowerCase()}${count > 1 ? 's' : ''}`).join(', ');

/** PII guardrail made visible: what was hidden, and exactly what the AI received. */
export function PiiNotice({ pii }) {
  const [open, setOpen] = useState(false);
  if (!pii?.entities?.length) return null;
  const parts = pii.maskedBody.split(/(\[(?:EMAIL|PHONE|IP|IBAN|CARD|ACCOUNT)\])/g);

  return (
    <section aria-label="Privacy" className="glass rise tone-ready" style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '12px 16px', borderRadius: 14, animationDelay: '.05s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <Icon name="shield" stroke="var(--green)" />
        <span style={{ fontSize: 13 }}><strong>Hidden before the AI saw it:</strong> {describe(pii.entities)}</span>
        <button className="btn-link" style={{ marginLeft: 'auto', fontSize: 12 }} onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? 'Hide' : 'Show what the AI saw'}
        </button>
      </div>
      {open && (
        <p className="fade mono" style={{ margin: 0, fontSize: 12, lineHeight: 1.7, color: 'var(--text-2)', whiteSpace: 'pre-line' }}>
          {parts.map((p, i) => (/^\[[A-Z]+\]$/.test(p)
            ? <span key={i} className="chip tone-ready" style={{ padding: '0 6px', fontSize: 11 }}>{p}</span>
            : <span key={i}>{p}</span>))}
        </p>
      )}
    </section>
  );
}
