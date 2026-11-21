export function ChartCard({ title, hint, children, className = '', delay = 0, action }) {
  return (
    <section className={`glass card rise ${className}`} style={{ animationDelay: `${delay}s` }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h2 className="card-title">{title}</h2>
        {hint && <span className="muted" style={{ fontSize: 12 }}>{hint}</span>}
        {action && <span style={{ marginLeft: 'auto' }}>{action}</span>}
      </div>
      {children}
    </section>
  );
}

/** Shared tooltip look for recharts. */
export const tooltipStyle = {
  contentStyle: { background: 'var(--glass-strong)', border: '1px solid var(--border-strong)', borderRadius: 12, backdropFilter: 'blur(16px)', color: 'var(--text)', fontSize: 12 },
  labelStyle: { color: 'var(--muted)' },
  itemStyle: { color: 'var(--text)' },
  cursor: { fill: 'var(--hover)' },
};
