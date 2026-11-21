import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage.jsx';
import { ConsolePage } from './pages/ConsolePage.jsx';
import { AgentPage } from './pages/AgentPage.jsx';

// Charts are heavy: load the Insights page only when it is opened.
const InsightsPage = lazy(() => import('./pages/InsightsPage.jsx').then((m) => ({ default: m.InsightsPage })));

export function App() {
  return (
    <Suspense fallback={<div className="empty">Loading…</div>}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/console" element={<ConsolePage />} />
        <Route path="/console/:ticketId" element={<ConsolePage />} />
        <Route path="/agent" element={<AgentPage />} />
        <Route path="/agent/:ticketId" element={<AgentPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
