import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Icon } from '../ui/Icon.jsx';
import { Dot } from '../ui/Tone.jsx';
import { ThemeToggle } from '../ui/ThemeToggle.jsx';
import { AmbientBackground } from './AmbientBackground.jsx';

/**
 * Sidebar + main area. Pages inject their own sidebar content (e.g. the inbox).
 * Desktop: fixed sidebar. Phone/tablet: top bar + slide-out sidebar.
 */
export function AppShell({ sidebar, onNewTicket, children }) {
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();
  useEffect(() => { setNavOpen(false); }, [location.pathname]);

  const brand = (
    <NavLink to="/" className="brand">
      <span className="brand-mark"><Icon name="shield" stroke="#fff" size={16} width={2.4} /></span>
      SentinelDesk
    </NavLink>
  );

  return (
    <>
      <AmbientBackground />
      <header className="mobile-bar glass">
        <button className="icon-btn press" onClick={() => setNavOpen(true)} aria-label="Open menu" aria-expanded={navOpen}>
          <Icon name="inbox" />
        </button>
        {brand}
        <button className="icon-btn press" onClick={onNewTicket} aria-label="New ticket" style={{ marginLeft: 'auto' }}>
          <Icon name="plus" />
        </button>
      </header>
      {navOpen && <div className="nav-scrim fade" onClick={() => setNavOpen(false)} aria-hidden="true" />}

      <div className="app">
        <aside className={`sidebar glass ${navOpen ? 'open' : ''}`} aria-label="Navigation">
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {brand}
            <button className="icon-btn press only-mobile" onClick={() => setNavOpen(false)} aria-label="Close menu" style={{ marginLeft: 'auto' }}>
              <Icon name="close" />
            </button>
          </div>
          <button className="btn press" onClick={() => { setNavOpen(false); onNewTicket(); }} style={{ justifyContent: 'flex-start', width: '100%' }}>
            <Icon name="plus" stroke="var(--accent-text)" /> New ticket <span className="kbd only-desktop" style={{ marginLeft: 'auto' }}>⌘K</span>
          </button>
          <nav className="nav" aria-label="Main">
            <NavLink to="/console"><Icon name="inbox" /> Console</NavLink>
            <NavLink to="/insights"><Icon name="chart" /> Insights</NavLink>
          </nav>
          <div className="scroll" style={{ flex: 1, minHeight: 0, margin: '0 -4px', padding: '0 4px' }} onClick={(e) => { if (e.target.closest('button[aria-current], li button')) setNavOpen(false); }}>
            {sidebar}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            <Dot tone="ready" pulse /> <span className="muted" style={{ fontSize: 12 }}>Live</span>
            <span style={{ marginLeft: 'auto' }}><ThemeToggle /></span>
          </div>
        </aside>
        <main className="main">{children}</main>
      </div>
    </>
  );
}
