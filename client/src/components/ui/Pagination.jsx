export function Pagination({ page, pages, total, limit, onPage }) {
  const from = total === 0 ? 0 : (page - 1) * limit + 1;
  const to = Math.min(total, page * limit);
  const btn = { width: 28, height: 28, borderRadius: 8, border: '1px solid var(--border-strong)', background: 'var(--glass-soft)' };
  return (
    <nav aria-label="Pages" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 8px 0', fontSize: 11 }} className="faint">
      <span>{from}–{to} of {total}</span>
      <button className="press" style={{ ...btn, marginLeft: 'auto' }} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">‹</button>
      <button className="press" style={btn} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">›</button>
    </nav>
  );
}
