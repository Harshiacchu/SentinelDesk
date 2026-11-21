import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AmbientBackground } from '../components/layout/AmbientBackground.jsx';
import { ThemeToggle } from '../components/ui/ThemeToggle.jsx';
import { Icon } from '../components/ui/Icon.jsx';
import { TicketComposer } from '../features/composer/TicketComposer.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { useMeta } from '../hooks/useMeta.js';
import { api } from '../api/sentinelApi.js';
import { SUPPORT_URL } from '../lib/links.js';

const STEPS = [
  ['01', 'Read', 'Detects English or German and hides emails, phones and IPs first.'],
  ['02', 'Sort', 'Type, department and urgency, each with how sure it is.'],
  ['03', 'Match', 'Finds the closest past tickets, in either language.'],
  ['04', 'Decide', 'Drafts a cited reply, or hands it to a person and says why.'],
];

export function HomePage() {
  const navigate = useNavigate();
  const meta = useMeta();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const { data: overview } = useAsync(() => api.analytics.overview(1), []);

  const submit = async (form) => {
    setBusy(true);
    setError(null);
    try { const t = await api.triage(form); navigate(`/console/${t.ticketId}`); } catch (err) { setError(err.message); setBusy(false); }
  };

  return (
    <>
      <AmbientBackground />
      <div style={{ position: 'relative', zIndex: 1, minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '20px 32px', maxWidth: 1200, width: '100%', margin: '0 auto' }}>
          <span className="brand"><span className="brand-mark"><Icon name="shield" stroke="#fff" width={2.4} /></span>SentinelDesk</span>
          <nav style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 22, fontSize: 14 }}>
            <Link to="/console" style={{ color: 'var(--text-2)' }}>Console</Link>
            <Link to="/insights" style={{ color: 'var(--text-2)' }}>Insights</Link>
            <Link to="/agent" style={{ color: 'var(--text-2)' }}>Agent portal</Link>
            <a href={SUPPORT_URL} target="_blank" rel="noreferrer" style={{ color: 'var(--text-2)' }}>Customer site ↗</a>
            <ThemeToggle />
          </nav>
        </header>

        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '56px 20px 64px', gap: 18 }}>
          {overview && (
            <span className="glass rise mono" style={{ padding: '6px 14px', borderRadius: 999, fontSize: 12, color: 'var(--muted)', boxShadow: 'none' }}>
              Last hour: {overview.kpis.total} tickets · {overview.kpis.escalated} handed to people · 0 made-up promises sent
            </span>
          )}
          <h1 className="title-grad rise" style={{ margin: 0, maxWidth: 860, textAlign: 'center', fontSize: 'clamp(36px, 6vw, 60px)', lineHeight: 1.05, fontWeight: 800, letterSpacing: '-0.04em', animationDelay: '.05s' }}>
            Paste a ticket.<br />Get a decision you can check.
          </h1>
          <p className="muted rise" style={{ margin: '0 0 18px', maxWidth: 580, textAlign: 'center', fontSize: 17, lineHeight: 1.55, animationDelay: '.1s' }}>
            Every answer points to the past tickets it came from. If there’s nothing to point to, it goes to a person.
          </p>
          <section className="glass card rise" style={{ width: 760, maxWidth: '100%', animationDelay: '.15s' }}>
            <TicketComposer branches={meta.branches} onSubmit={submit} busy={busy} error={error} />
          </section>
          <section style={{ marginTop: 72, width: 1000, maxWidth: '100%', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
            {STEPS.map(([n, title, text], i) => (
              <div key={n} className="glass card-sm lift rise" style={{ display: 'flex', flexDirection: 'column', gap: 8, animationDelay: `${0.2 + i * 0.06}s` }}>
                <span className="mono faint" style={{ fontSize: 12 }}>{n}</span>
                <strong style={{ fontSize: 17 }}>{title}</strong>
                <span className="muted" style={{ fontSize: 14, lineHeight: 1.5 }}>{text}</span>
              </div>
            ))}
          </section>
        </main>
      </div>
    </>
  );
}
