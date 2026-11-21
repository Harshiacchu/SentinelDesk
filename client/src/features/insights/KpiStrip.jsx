import { duration, percent } from '../../lib/format.js';

export function KpiStrip({ kpis }) {
  const items = [
    { label: 'Tickets', value: kpis.total, hint: 'in the last 6 hours' },
    { label: 'Answered automatically', value: kpis.total ? percent(kpis.autoDrafted / kpis.total) : '—', hint: `${kpis.autoDrafted} tickets, each with sources` },
    { label: 'Sent to an engineer', value: kpis.escalated, hint: 'outages, risky asks, unclear cases' },
    { label: 'Time to triage', value: duration(kpis.p50Ms), hint: `slowest 5%: ${duration(kpis.p95Ms)}` },
    { label: 'AI was right', value: kpis.agreement === null ? '—' : percent(kpis.agreement), hint: `from ${kpis.feedbackCount} engineer reviews` },
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
