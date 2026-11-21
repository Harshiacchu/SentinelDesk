import { duration, percent } from '../../lib/format.js';

export function KpiStrip({ kpis }) {
  const items = [
    { label: 'Tickets', value: kpis.total, hint: 'last 6 hours' },
    { label: 'Sent to a person', value: kpis.total ? percent(kpis.escalated / kpis.total) : '—', hint: `${kpis.escalated} escalated` },
    { label: 'Auto-drafted', value: kpis.autoDrafted, hint: 'cited and checked' },
    { label: 'p95 latency', value: duration(kpis.p95Ms), hint: `median ${duration(kpis.p50Ms)}` },
    { label: 'Operators agreed', value: kpis.agreement === null ? '—' : percent(kpis.agreement), hint: `${kpis.feedbackCount} reviews` },
  ];
  return (
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 14 }}>
      {items.map((k, i) => (
        <div key={k.label} className="glass card-sm rise" style={{ display: 'flex', flexDirection: 'column', gap: 4, animationDelay: `${i * 0.05}s` }}>
          <span className="eyebrow">{k.label}</span>
          <span style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em' }}>{k.value}</span>
          <span className="muted" style={{ fontSize: 12 }}>{k.hint}</span>
        </div>
      ))}
    </section>
  );
}
