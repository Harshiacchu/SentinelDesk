import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AmbientBackground } from '../components/layout/AmbientBackground.jsx';
import { ThemeToggle } from '../components/ui/ThemeToggle.jsx';
import { Icon } from '../components/ui/Icon.jsx';
import { Dot } from '../components/ui/Tone.jsx';
import { MessageThread } from '../features/conversation/MessageThread.jsx';
import { MessageComposer } from '../features/conversation/MessageComposer.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { useEventStream } from '../hooks/useEventStream.js';
import { useMeta } from '../hooks/useMeta.js';
import { api } from '../api/sentinelApi.js';

const STAGE = {
  answered_by_ai: { tone: 'ready', label: 'Answered' },
  waiting_for_agent: { tone: 'review', label: 'Waiting for an agent' },
  with_agent: { tone: 'info', label: 'Chatting with an agent' },
  resolved: { tone: 'ready', label: 'Resolved' },
};

/** Customer-facing page: ask for help, get an AI answer or a live agent, chat until resolved. */
export function SupportPage() {
  const { ticketId } = useParams();
  const [params] = useSearchParams();
  const key = params.get('key') ?? '';
  return (
    <>
      <AmbientBackground />
      <div style={{ position: 'relative', zIndex: 1, minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 20px', maxWidth: 860, width: '100%', margin: '0 auto' }}>
          <Link to="/support" className="brand"><span className="brand-mark"><Icon name="shield" stroke="#fff" width={2.4} /></span>Support</Link>
          <span style={{ marginLeft: 'auto' }}><ThemeToggle /></span>
        </header>
        <main style={{ flex: 1, width: '100%', maxWidth: 860, margin: '0 auto', padding: '8px 16px 40px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {ticketId ? <Conversation ticketId={ticketId} accessKey={key} /> : <NewRequest />}
        </main>
      </div>
    </>
  );
}

function NewRequest() {
  const navigate = useNavigate();
  const meta = useMeta();
  const [form, setForm] = useState({ subject: '', body: '', branch: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.support.open({ ...form, branch: form.branch || meta.branches[0] });
      navigate(`/support/${res.ticketId}?key=${res.key}`);
    } catch (err) { setError(err.message); setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="glass card rise" style={{ gap: 14 }}>
      <div>
        <h1 className="title-grad" style={{ margin: '0 0 6px', fontSize: 30, fontWeight: 800, letterSpacing: '-0.03em' }}>How can we help?</h1>
        <p className="muted" style={{ margin: 0, lineHeight: 1.5 }}>Write in English or German. You’ll get an answer here, from our assistant or a person.</p>
      </div>
      <input className="field" placeholder="Subject (optional)" aria-label="Subject (optional)" value={form.subject} onChange={set('subject')} />
      <textarea className="field" rows={5} placeholder="Describe the problem…" aria-label="Your message" value={form.body} onChange={set('body')} style={{ resize: 'vertical', fontSize: 15, lineHeight: 1.5 }} />
      <select className="field" aria-label="Your office" value={form.branch} onChange={set('branch')}>
        <option value="">Your office (optional)</option>
        {meta.branches.map((b) => <option key={b} value={b}>{b}</option>)}
      </select>
      {error && <p className="error-box" style={{ margin: 0 }}>{error}</p>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="faint" style={{ fontSize: 12 }}>Emails and phone numbers are hidden from the AI.</span>
        <button className="btn btn-accent press" disabled={busy || !form.body.trim()} style={{ marginLeft: 'auto', padding: '11px 20px' }}>
          {busy ? <span className="shimmer" style={{ WebkitTextFillColor: 'transparent' }}>Sending…</span> : 'Send'}
        </button>
      </div>
    </form>
  );
}

function Conversation({ ticketId, accessKey }) {
  const { data, error, reload } = useAsync(() => api.support.view(ticketId, accessKey), [ticketId, accessKey]);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  useEventStream(api.support.eventsUrl(ticketId, accessKey), ['message', 'update'], useCallback(() => reload({ quiet: true }), [reload]));

  if (error) return <p className="error-box">This link isn’t valid. Check that you copied the whole address.</p>;
  if (!data) return <div className="skeleton" style={{ height: 360 }} />;

  const stage = STAGE[data.stage];
  const act = async (fn) => { setBusy(true); try { await fn(); await reload({ quiet: true }); } finally { setBusy(false); } };
  const copy = () => { navigator.clipboard?.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 1500); };

  return (
    <>
      <section className="glass rise" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', borderRadius: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          <strong style={{ fontSize: 16, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{data.subject || 'Your request'}</strong>
          <span className="muted mono" style={{ fontSize: 12 }}>{data.ticketId}</span>
        </div>
        <span className={`chip tone-${stage.tone}`} style={{ marginLeft: 'auto' }}><Dot tone={stage.tone} pulse={data.stage === 'waiting_for_agent'} size={7} /> {stage.label}</span>
        <button className="btn press" onClick={copy} style={{ padding: '7px 12px' }}>{copied ? 'Link copied' : 'Copy link'}</button>
      </section>

      <section className="glass card rise" style={{ animationDelay: '.06s' }}>
        <MessageThread messages={data.messages} viewer="customer" maxHeight={520} />
        {data.stage === 'answered_by_ai' && (
          <div className="fade" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', paddingTop: 10, borderTop: '1px solid var(--border)' }}>
            <span className="muted" style={{ fontSize: 13 }}>Didn’t solve it?</span>
            <button className="btn press" disabled={busy} onClick={() => act(() => api.support.person(ticketId, accessKey))}>Talk to a person</button>
          </div>
        )}
        <MessageComposer lang={data.language} busy={busy} onSend={(text) => act(() => api.support.say(ticketId, accessKey, text))}
          placeholder={data.stage === 'with_agent' ? `Message ${data.agentName}…` : 'Write a message…'} />
      </section>
      <p className="faint" style={{ margin: 0, fontSize: 12, textAlign: 'center' }}>Keep this link to come back to the conversation.</p>
    </>
  );
}
