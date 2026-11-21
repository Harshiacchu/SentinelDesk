import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell.jsx';
import { KpiStrip } from '../features/insights/KpiStrip.jsx';
import { ChartCard } from '../features/insights/ChartCard.jsx';
import { VolumeChart } from '../features/insights/VolumeChart.jsx';
import { SeverityDonut } from '../features/insights/SeverityDonut.jsx';
import { HorizontalBars } from '../features/insights/HorizontalBars.jsx';
import { BranchHeatmap } from '../features/insights/BranchHeatmap.jsx';
import { OutageMap } from '../features/insights/OutageMap.jsx';
import { OutageBanner } from '../features/incidents/OutageBanner.jsx';
import { IncidentDrawer } from '../features/incidents/IncidentDrawer.jsx';
import { CommandPalette } from '../features/composer/CommandPalette.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { useLiveEvents } from '../hooks/useLiveEvents.js';
import { useHotkey } from '../hooks/useHotkey.js';
import { useMeta } from '../hooks/useMeta.js';
import { reasonInfo } from '../lib/severity.js';
import { api } from '../api/sentinelApi.js';

const WINDOWS = [15, 60, 240];
const REASON_COLOR = { 'tone-critical': 'red', 'tone-review': 'amber' };

export function InsightsPage() {
  const navigate = useNavigate();
  const meta = useMeta();
  const [minutes, setMinutes] = useState(60);
  const [tracking, setTracking] = useState(null);
  const [palette, setPalette] = useState(false);

  const overview = useAsync(() => api.analytics.overview(6), []);
  const heatmap = useAsync(() => api.analytics.heatmap(minutes), [minutes]);
  const incidents = useAsync(() => api.incidents.active(), []);

  const timer = useRef(null);
  useLiveEvents(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { overview.reload({ quiet: true }); heatmap.reload({ quiet: true }); incidents.reload({ quiet: true }); }, 500);
  });
  useHotkey('k', useCallback(() => setPalette(true), []));

  const o = overview.data;
  const windowPicker = (
    <div className="seg" role="group" aria-label="Time window">
      {WINDOWS.map((m) => <button key={m} aria-pressed={minutes === m} onClick={() => setMinutes(m)}>{m < 60 ? `${m}m` : `${m / 60}h`}</button>)}
    </div>
  );

  return (
    <AppShell onNewTicket={() => setPalette(true)}>
      <header className="rise" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="eyebrow">Insights</span>
        <h1 className="title-grad" style={{ margin: 0, fontSize: 32, fontWeight: 800, letterSpacing: '-0.03em' }}>What’s happening across the desk</h1>
      </header>
      <OutageBanner incidents={incidents.data?.items} onTrack={setTracking} />
      {overview.error && <p className="error-box">{overview.error.message}</p>}
      {o && <KpiStrip kpis={o.kpis} />}

      <div className="insights-grid">
        <ChartCard className="span-12" title="Outage map" hint={`Live incidents per office, last ${minutes < 60 ? `${minutes} min` : `${minutes / 60} h`}`} action={windowPicker} delay={0.1}>
          {heatmap.data ? <OutageMap sites={heatmap.data.sites} /> : <div className="skeleton" style={{ height: 240 }} />}
        </ChartCard>
        <ChartCard className="span-12" title="Branch heatmap" hint="Which offices report the same kind of incident right now" delay={0.14}>
          {heatmap.data ? <BranchHeatmap data={heatmap.data} /> : <div className="skeleton" style={{ height: 300 }} />}
        </ChartCard>
        <ChartCard className="span-8" title="Ticket volume" hint="by decision, every 30 min" delay={0.18}>
          {o ? <VolumeChart volume={o.volume} /> : <div className="skeleton" style={{ height: 260 }} />}
        </ChartCard>
        <ChartCard className="span-4" title="Decisions" hint="last 6 hours" delay={0.22}>
          {o && <SeverityDonut severity={o.severity} />}
        </ChartCard>
        <ChartCard className="span-6" title="Departments" hint="where tickets were routed" delay={0.26}>
          {o && <HorizontalBars data={o.queues} />}
        </ChartCard>
        <ChartCard className="span-6" title="Why tickets went to a person" hint="gate checks that fired" delay={0.3}>
          {o && <HorizontalBars data={o.reasons.map((r) => ({ ...r, name: reasonInfo(r.code).title }))}
            colorFor={(d, c) => c[REASON_COLOR[reasonInfo(d.code).tone] ?? 'blue']} />}
        </ChartCard>
      </div>

      <IncidentDrawer incidentKey={tracking} onClose={() => setTracking(null)} onOpenTicket={(id) => navigate(`/console/${id}`)} />
      <CommandPalette open={palette} onClose={() => setPalette(false)} branches={meta.branches}
        onTriage={async (form) => { const t = await api.triage(form); navigate(`/console/${t.ticketId}`); }} />
    </AppShell>
  );
}
