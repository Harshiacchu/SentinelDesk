import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell.jsx';
import { TicketHeader } from '../features/ticket/TicketHeader.jsx';
import { AgentQueue } from '../features/agent/AgentQueue.jsx';
import { AssistPanel } from '../features/agent/AssistPanel.jsx';
import { MessageThread } from '../features/conversation/MessageThread.jsx';
import { MessageComposer } from '../features/conversation/MessageComposer.jsx';
import { ChatWidget } from '../features/chat/ChatWidget.jsx';
import { CommandPalette } from '../features/composer/CommandPalette.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { useLiveEvents } from '../hooks/useLiveEvents.js';
import { useHotkey } from '../hooks/useHotkey.js';
import { useMeta } from '../hooks/useMeta.js';
import { useAgentName } from '../hooks/useAgentName.js';
import { api } from '../api/sentinelApi.js';

/** Live agent portal: tickets the AI could not safely answer, with a triage assist beside each. */
export function AgentPage() {
  const { ticketId } = useParams();
  const navigate = useNavigate();
  const meta = useMeta();
  const [agent, setAgent] = useAgentName();
  const [view, setView] = useState('unclaimed');
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [palette, setPalette] = useState(false);

  const queue = useAsync(() => (agent ? api.agent.queue({ view, agent, page }) : Promise.resolve(null)), [view, agent, page]);
  const ticket = useAsync(() => (ticketId ? api.tickets.get(ticketId) : Promise.resolve(null)), [ticketId]);
  const assist = useAsync(() => (ticketId ? api.agent.assist(ticketId) : Promise.resolve(null)), [ticketId]);

  const timer = useRef(null);
  useLiveEvents((name, data) => {
    if (name === 'ticket.message' && data?.ticketId === ticketId) ticket.reload({ quiet: true });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => queue.reload({ quiet: true }), 300);
  });
  useHotkey('k', useCallback(() => setPalette(true), []));

  useEffect(() => { setError(null); }, [ticketId]);

  const act = async (fn, nextView) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      if (nextView) { setView(nextView); setPage(1); }
      await Promise.all([ticket.reload({ quiet: true }), queue.reload({ quiet: true })]);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  if (!agent) return <SignIn onSave={setAgent} />;

  const t = ticket.data;
  const mine = t?.assignee === agent;
  const done = t && (t.status === 'resolved' || t.status === 'sent');

  return (
    <AppShell
      onNewTicket={() => setPalette(true)}
      sidebar={(
        <AgentQueue agent={agent} onRename={() => setAgent('')} view={view} onView={(v) => { setView(v); setPage(1); }}
          data={queue.data} loading={queue.loading} selectedId={ticketId} onSelect={(id) => navigate(`/agent/${id}`)} onPage={setPage} />
      )}
    >
      {!ticketId && (
        <section className="glass card rise" style={{ alignItems: 'flex-start' }}>
          <span className="eyebrow">Live agent portal</span>
          <h1 className="title-grad" style={{ margin: 0, fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em' }}>Tickets the AI handed to a person</h1>
          <p className="muted" style={{ margin: 0, lineHeight: 1.6, maxWidth: 620 }}>
            When there’s no safe precedent, a risky request, or an outage, the ticket lands here. Pick one from the queue: the triage assist explains why, lists the facts and steps, and helps you write the reply.
          </p>
        </section>
      )}
      {ticket.error && <p className="error-box">{ticket.error.message}</p>}
      {error && <p className="error-box">{error}</p>}
      {t && (
        <>
          <TicketHeader ticket={t} />
          <ClaimBar ticket={t} agent={agent} busy={busy}
            onClaim={() => act(() => api.agent.claim(t.ticketId, agent), 'mine')}
            onRelease={() => act(() => api.agent.release(t.ticketId, agent), 'unclaimed')} />
          <div className="ticket-grid">
            <div className="ticket-left">
              <section aria-label="Conversation" className="glass card rise">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h2 className="card-title">Conversation</h2>
                  <span className="muted" style={{ fontSize: 12 }}>with the customer · {t.language === 'de' ? 'German' : 'English'}</span>
                  {mine && !done && (
                    <button className="btn press" style={{ marginLeft: 'auto', padding: '7px 12px' }} disabled={busy}
                      onClick={() => act(() => api.agent.resolve(t.ticketId, agent), 'resolved')}>Resolve</button>
                  )}
                </div>
                <MessageThread messages={t.messages ?? []} viewer="agent" maxHeight={420} />
                {mine && assist.data && (
                  <MessageComposer key={t.ticketId} lang={assist.data.language} busy={busy} phrases={assist.data.phrases}
                    starter={(t.messages ?? []).some((m) => m.from === 'agent') ? '' : assist.data.replyStarter}
                    placeholder="Message the customer…" onSend={(text) => act(() => api.agent.message(t.ticketId, agent, text))} />
                )}
              </section>
              {!mine && !done && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Claim the ticket to chat with the customer.</p>}
            </div>
            <aside className="ticket-right" style={{ maxWidth: 380 }}>
              {assist.data ? <AssistPanel assist={assist.data} onOpenRelated={(id) => navigate(`/agent/${id}`)} /> : <div className="skeleton" style={{ height: 320 }} />}
            </aside>
          </div>
        </>
      )}
      <ChatWidget ticket={t} suggestions={meta.chatSuggestions} />
      <CommandPalette open={palette} onClose={() => setPalette(false)} branches={meta.branches}
        onTriage={async (form) => { const created = await api.triage(form); navigate(created.severity === 'ready' ? `/console/${created.ticketId}` : `/agent/${created.ticketId}`); }} />
    </AppShell>
  );
}

function ClaimBar({ ticket, agent, busy, onClaim, onRelease }) {
  const done = ticket.status === 'resolved' || ticket.status === 'sent';
  let text;
  let action = null;
  if (done) text = `Resolved${ticket.assignee ? ` by ${ticket.assignee}` : ''}.`;
  else if (!ticket.assignee) { text = 'Nobody is working on this yet.'; action = <button className="btn btn-accent press" disabled={busy} onClick={onClaim}>Claim ticket</button>; }
  else if (ticket.assignee === agent) { text = 'You’re working on this ticket.'; action = <button className="btn press" disabled={busy} onClick={onRelease}>Release</button>; }
  else text = `${ticket.assignee} is working on this ticket.`;
  return (
    <div className="glass rise" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderRadius: 14, flexWrap: 'wrap' }}>
      <span style={{ fontSize: 14 }}>{text}</span>
      <span style={{ marginLeft: 'auto' }}>{action}</span>
    </div>
  );
}

function SignIn({ onSave }) {
  const [name, setName] = useState('');
  return (
    <AppShell onNewTicket={() => {}}>
      <form className="glass card rise" style={{ maxWidth: 460, margin: '10vh auto 0' }} onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSave(name); }}>
        <span className="eyebrow">Live agent portal</span>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>What’s your name?</h1>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>Shown when you claim and reply to tickets.</p>
        <input className="field" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Priya" aria-label="Your name" />
        <button className="btn btn-accent press" disabled={!name.trim()}>Start</button>
      </form>
    </AppShell>
  );
}
