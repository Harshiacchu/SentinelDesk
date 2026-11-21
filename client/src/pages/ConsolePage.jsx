import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell.jsx';
import { InboxPanel } from '../features/inbox/InboxPanel.jsx';
import { TicketView } from '../features/ticket/TicketView.jsx';
import { OutageBanner } from '../features/incidents/OutageBanner.jsx';
import { IncidentDrawer } from '../features/incidents/IncidentDrawer.jsx';
import { ChatWidget } from '../features/chat/ChatWidget.jsx';
import { CommandPalette } from '../features/composer/CommandPalette.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { useLiveEvents } from '../hooks/useLiveEvents.js';
import { useHotkey } from '../hooks/useHotkey.js';
import { useMeta } from '../hooks/useMeta.js';
import { api } from '../api/sentinelApi.js';

/** Container: owns data fetching and wiring; children are presentational. */
export function ConsolePage() {
  const { ticketId } = useParams();
  const navigate = useNavigate();
  const meta = useMeta();
  const [filter, setFilter] = useState('needs');
  const [page, setPage] = useState(1);
  const [palette, setPalette] = useState(false);
  const [tracking, setTracking] = useState(null);
  const [busy, setBusy] = useState(false);

  const inbox = useAsync(() => api.tickets.list({ filter, page }), [filter, page]);
  const incidents = useAsync(() => api.incidents.active(), []);
  const ticket = useAsync(() => (ticketId ? api.tickets.get(ticketId) : Promise.resolve(null)), [ticketId]);

  // Auto-open the top ticket when none is selected.
  useEffect(() => {
    if (!ticketId && inbox.data?.items[0]) navigate(`/console/${inbox.data.items[0].ticketId}`, { replace: true });
  }, [ticketId, inbox.data, navigate]);

  // Live updates, debounced so a burst of events triggers one refresh.
  const timer = useRef(null);
  useLiveEvents(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      inbox.reload({ quiet: true });
      incidents.reload({ quiet: true });
      if (ticketId) ticket.reload({ quiet: true });
    }, 300);
  });

  useHotkey('k', useCallback(() => setPalette(true), []));

  const incident = useMemo(
    () => incidents.data?.items.find((i) => i.key === ticket.data?.incidentKey) ?? null,
    [incidents.data, ticket.data],
  );

  const mutate = async (fn) => {
    setBusy(true);
    try { await fn(); await Promise.all([ticket.reload({ quiet: true }), inbox.reload({ quiet: true })]); } finally { setBusy(false); }
  };

  const triage = async (form) => {
    const created = await api.triage(form);
    setFilter(created.severity === 'ready' ? 'ready' : 'needs');
    setPage(1);
    navigate(`/console/${created.ticketId}`);
    incidents.reload({ quiet: true });
  };

  return (
    <AppShell
      onNewTicket={() => setPalette(true)}
      sidebar={(
        <InboxPanel
          filter={filter} onFilter={(f) => { setFilter(f); setPage(1); }}
          data={inbox.data} loading={inbox.loading}
          selectedId={ticketId} onSelect={(id) => navigate(`/console/${id}`)} onPage={setPage}
        />
      )}
    >
      <OutageBanner incidents={incidents.data?.items} onTrack={setTracking} />
      {ticket.error && <p className="error-box">{ticket.error.message}</p>}
      {!ticket.data && ticket.loading && <div className="skeleton" style={{ height: 320 }} />}
      {!ticketId && inbox.data?.items.length === 0 && <p className="empty">Inbox is empty. Press ⌘K to triage a ticket.</p>}
      {ticket.data && (
        <TicketView
          ticket={ticket.data} incident={incident} busy={busy}
          onAction={(action) => mutate(() => api.tickets.act(ticket.data.ticketId, action))}
          onFeedback={(verdict) => mutate(() => api.tickets.feedback(ticket.data.ticketId, verdict))}
          onAddNote={(text) => mutate(() => api.tickets.note(ticket.data.ticketId, text))}
          onTrackIncident={setTracking}
        />
      )}
      <IncidentDrawer incidentKey={tracking} onClose={() => setTracking(null)} onOpenTicket={(id) => { setTracking(null); navigate(`/console/${id}`); }} />
      <ChatWidget ticket={ticket.data} suggestions={meta.chatSuggestions} />
      <CommandPalette open={palette} onClose={() => setPalette(false)} onTriage={triage} />
    </AppShell>
  );
}
