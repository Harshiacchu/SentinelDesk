import { clock } from '../../lib/format.js';

/** "Was the AI right?" feeds the review log and the agreement KPI on Insights. */
export function FeedbackCard({ ticket, onFeedback, busy }) {
  const last = ticket.feedback[ticket.feedback.length - 1]?.verdict;
  const recent = [...ticket.activity].reverse().slice(0, 3);
  const pill = (active) => ({
    padding: '7px 18px', borderRadius: 999, fontSize: 13, fontWeight: 600,
    border: active ? '1px solid transparent' : '1px solid var(--border-strong)',
    background: active ? 'linear-gradient(135deg, var(--accent), var(--accent-2))' : 'var(--glass-soft)',
    color: active ? '#fff' : 'var(--text-2)',
  });
  return (
    <section className="glass card rise" style={{ padding: '18px 20px', gap: 10, animationDelay: '.26s' }}>
      <span style={{ fontSize: 13, color: 'var(--text-2)' }}>Was the AI right?</span>
      <span style={{ display: 'flex', gap: 8 }}>
        <button className="press" style={pill(last === 'right')} disabled={busy} onClick={() => onFeedback('right')}>Yes</button>
        <button className="press" style={pill(last === 'wrong')} disabled={busy} onClick={() => onFeedback('wrong')}>No</button>
      </span>
      <ol className="list" style={{ display: 'flex', flexDirection: 'column', gap: 9, marginTop: 6 }}>
        {recent.map((a, i) => (
          <li key={i} className="fade muted" style={{ fontSize: 12 }}>
            <strong style={{ color: 'var(--text-2)', fontWeight: 600 }}>{a.who}</strong> · {a.what} · {clock(a.at)}
          </li>
        ))}
      </ol>
    </section>
  );
}
