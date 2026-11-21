import { useEffect, useRef } from 'react';
import { clock } from '../../lib/format.js';

/**
 * Chat thread shared by the customer page and the agent portal.
 * `viewer` decides which side is "me": 'customer' or 'agent'.
 */
export function MessageThread({ messages, viewer, maxHeight = 460 }) {
  const end = useRef(null);
  // Block body on purpose: scrollIntoView returns a Promise in current browsers, which React would treat as a cleanup.
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [messages.length]);

  return (
    <ol className="list scroll" aria-live="polite" style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight, padding: '4px 2px' }}>
      {messages.map((m) => <Bubble key={m.id} m={m} mine={m.from === viewer || (viewer === 'agent' && m.from === 'agent')} viewer={viewer} />)}
      <li ref={end} aria-hidden="true" />
    </ol>
  );
}

function Bubble({ m, mine, viewer }) {
  if (m.from === 'system') {
    return (
      <li className="fade" style={{ alignSelf: 'center', maxWidth: '85%', textAlign: 'center', fontSize: 12, lineHeight: 1.5, color: 'var(--muted)', padding: '4px 10px' }}>
        {m.text}
      </li>
    );
  }
  const label = m.from === 'customer' ? (viewer === 'customer' ? 'You' : 'Customer') : m.from === 'ai' ? 'SentinelDesk AI' : (m.name ?? 'Agent');
  const bubble = mine
    ? { background: 'linear-gradient(135deg, var(--accent), var(--accent-2))', color: '#fff', borderRadius: '16px 16px 4px 16px' }
    : { background: 'var(--glass-soft)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: '16px 16px 16px 4px' };
  return (
    <li className="rise" style={{ alignSelf: mine ? 'flex-end' : 'flex-start', maxWidth: '82%', display: 'flex', flexDirection: 'column', gap: 4, alignItems: mine ? 'flex-end' : 'flex-start' }}>
      <span className="faint" style={{ fontSize: 11 }}>
        {label}{m.from === 'ai' && <span className="chip tone-info" style={{ marginLeft: 6, padding: '1px 7px', fontSize: 10 }}>AI</span>} · {clock(m.at)}
      </span>
      <span style={{ ...bubble, padding: '10px 14px', fontSize: 14, lineHeight: 1.55, whiteSpace: 'pre-line' }}>{m.text}</span>
      {m.sources?.length > 0 && <span className="faint mono" style={{ fontSize: 10 }}>based on {m.sources.join(', ')}</span>}
    </li>
  );
}
