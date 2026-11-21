import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/sentinelApi.js';
import { Icon } from '../../components/ui/Icon.jsx';

const sparkle = { width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 18px rgba(99,102,241,0.55)', flex: 'none' };

/** Collapsible assistant scoped to the open ticket. Answers come only from its evidence. */
export function ChatWidget({ ticket, suggestions = [] }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const end = useRef(null);

  useEffect(() => setMessages([]), [ticket?.ticketId]);
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth' }), [messages]);

  const ask = async (question) => {
    if (!ticket || !question.trim()) return;
    setMessages((m) => [...m, { role: 'user', text: question }]);
    setText('');
    setBusy(true);
    try {
      const res = await api.tickets.chat(ticket.ticketId, question);
      setMessages((m) => [...m, { role: 'bot', text: res.answer }]);
    } catch (err) {
      setMessages((m) => [...m, { role: 'bot', text: err.message, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ position: 'fixed', right: 'max(16px, env(safe-area-inset-right))', bottom: 'max(16px, env(safe-area-inset-bottom))', zIndex: 30, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 12 }}>
      {open && (
        <section aria-label="Ask SentinelDesk" className="glass-strong pop" style={{ width: 380, maxWidth: 'calc(100vw - 32px)', borderRadius: 20, boxShadow: '0 30px 70px rgba(0,0,0,0.45)', display: 'flex', flexDirection: 'column', overflow: 'hidden', transformOrigin: 'bottom right' }}>
          <header style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 18px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ ...sparkle, width: 26, height: 26, borderRadius: 8 }}><Icon name="sparkle" stroke="#fff" size={14} /></span>
            <span style={{ display: 'flex', flexDirection: 'column' }}>
              <strong style={{ fontSize: 14 }}>Ask about this ticket</strong>
              <span className="muted" style={{ fontSize: 11 }}>answers only from past resolved tickets</span>
            </span>
          </header>
          <div className="scroll" style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 180, maxHeight: 340 }}>
            {!ticket && <span className="muted">Open a ticket first.</span>}
            {ticket && messages.length === 0 && <span className="muted" style={{ fontSize: 13 }}>Ask anything about “{ticket.subject || ticket.ticketId}”.</span>}
            {messages.map((m, i) => (
              <span key={i} className={m.role === 'user' ? 'fade' : 'rise'} style={m.role === 'user'
                ? { alignSelf: 'flex-end', maxWidth: '85%', padding: '9px 13px', borderRadius: '14px 14px 4px 14px', background: 'linear-gradient(135deg, var(--accent), var(--accent-2))', color: '#fff', fontSize: 13 }
                : { alignSelf: 'flex-start', maxWidth: '92%', padding: '11px 13px', borderRadius: '14px 14px 14px 4px', background: 'var(--glass-soft)', border: '1px solid var(--border)', fontSize: 13, lineHeight: 1.55, whiteSpace: 'pre-line', color: m.error ? 'var(--red-text)' : 'var(--text)' }}>
                {m.text}
              </span>
            ))}
            {busy && <span className="shimmer" style={{ fontSize: 12 }}>Looking through the evidence…</span>}
            <span ref={end} />
          </div>
          {ticket && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '0 18px 12px' }}>
              {suggestions.map((s) => <button key={s.id} className="btn press" style={{ padding: '6px 11px', borderRadius: 999, fontSize: 12, fontWeight: 500 }} onClick={() => ask(s.label)}>{s.label}</button>)}
            </div>
          )}
          <form onSubmit={(e) => { e.preventDefault(); ask(text); }} style={{ display: 'flex', gap: 8, padding: '12px 18px 16px', borderTop: '1px solid var(--border)' }}>
            <input className="field" aria-label="Ask a question" placeholder="Ask a question…" value={text} onChange={(e) => setText(e.target.value)} disabled={!ticket} />
            <button className="btn btn-accent press" disabled={!ticket || busy || !text.trim()}>Ask</button>
          </form>
        </section>
      )}
      <button className="glass press" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 10, padding: '10px 18px 10px 10px', borderRadius: 999, fontSize: 13, fontWeight: 600 }}>
        <span style={sparkle}><Icon name={open ? 'close' : 'sparkle'} stroke="#fff" size={14} /></span>
        {open ? 'Close' : 'Ask SentinelDesk'}
      </button>
    </div>
  );
}
