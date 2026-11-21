import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell.jsx';
import { KpiStrip } from '../features/insights/KpiStrip.jsx';
import { ChartCard } from '../features/insights/ChartCard.jsx';
import { VolumeChart } from '../features/insights/VolumeChart.jsx';
import { SeverityDonut } from '../features/insights/SeverityDonut.jsx';
import { HorizontalBars } from '../features/insights/HorizontalBars.jsx';
import { ProblemHeatmap } from '../features/insights/ProblemHeatmap.jsx';
import { OutageBanner } from '../features/incidents/OutageBanner.jsx';
import { IncidentDrawer } from '../features/incidents/IncidentDrawer.jsx';
import { CommandPalette } from '../features/composer/CommandPalette.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { useLiveEvents } from '../hooks/useLiveEvents.js';
import { useHotkey } from '../hooks/useHotkey.js';
import { reasonInfo } from '../lib/severity.js';
import { api } from '../api/sentinelApi.js';

const REASON_COLOR = { 'tone-critical': 'red', 'tone-review': 'amber' };

/** One question per card, in plain words. */
export function InsightsPage() {
  const navigate = useNavigate();
  const [tracking, setTracking] = useState(null);
  const [palette, setPalette] = useState(false);

  const overview = useAsync(() => api.analytics.overview(6), []);
  const heatmap = useAsync(() => api.analytics.heatmap(6), []);
  const incidents = useAsync(() => api.incidents.active(), []);

  const timer = useRef(null);
  useLiveEvents(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { overview.reload({ quiet: true }); heatmap.reload({ quiet: true }); incidents.reload({ quiet: true }); }, 500);
  });
  useHotkey('k', useCallback(() => setPalette(true), []));

  const o = overview.data;
  return (
    <AppShell onNewTicket={() => setPalette(true)}>
      <header className="rise" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="eyebrow">Insights · last 6 hours</span>
        <h1 className="title-grad" style={{ margin: 0, fontSize: 32, fontWeight: 800, letterSpacing: '-0.03em' }}>How the desk is doing</h1>
      </header>
      <OutageBanner incidents={incidents.data?.items} onTrack={setTracking} />
      {overview.error && <p className="error-box">{overview.error.message}</p>}
      {o && <KpiStrip kpis={o.kpis} />}

      <div className="insights-grid">
        <ChartCard className="span-12" title="When did problems spike?" hint="Each square = incidents of one type in one hour" delay={0.1}>
          {heatmap.data ? <ProblemHeatmap data={heatmap.data} /> : <div className="skeleton" style={{ height: 280 }} />}
        </ChartCard>
        <ChartCard className="span-8" title="Tickets over time" hint="every 30 minutes" delay={0.14}>
          {o ? <VolumeChart volume={o.volume} /> : <div className="skeleton" style={{ height: 260 }} />}
        </ChartCard>
        <ChartCard className="span-4" title="How tickets were handled" delay={0.18}>
          {o && <SeverityDonut severity={o.severity} />}
        </ChartCard>
        <ChartCard className="span-6" title="Most common problems" delay={0.22}>
          {o && <HorizontalBars data={o.topics} />}
        </ChartCard>
        <ChartCard className="span-6" title="Why tickets went to an engineer" delay={0.26}>
          {o && <HorizontalBars data={o.reasons.map((r) => ({ ...r, name: reasonInfo(r.code).title }))}
            colorFor={(d, c) => c[REASON_COLOR[reasonInfo(d.code).tone] ?? 'blue']} />}
        </ChartCard>
      </div>

      <IncidentDrawer incidentKey={tracking} onClose={() => setTracking(null)} onOpenTicket={(id) => navigate(`/console/${id}`)} />
      <CommandPalette open={palette} onClose={() => setPalette(false)}
        onTriage={async (form) => { const t = await api.triage(form); navigate(`/console/${t.ticketId}`); }} />
    </AppShell>
  );
}
