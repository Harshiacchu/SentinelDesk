import { Drawer } from '../../components/ui/Drawer.jsx';
import { ActivityRings } from '../../components/ui/ActivityRings.jsx';
import { ConfidenceBar, Dot } from '../../components/ui/Tone.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { api } from '../../api/sentinelApi.js';
import { useTheme } from '../../theme/ThemeContext.jsx';
import { timeAgo } from '../../lib/format.js';

/** Tracks one outage: rings, which branches, and every similar ticket (click to open). */
export function IncidentDrawer({ incidentKey, onClose, onOpenTicket }) {
  const { colors } = useTheme();
  const { data, loading, error } = useAsync(() => (incidentKey ? api.incidents.get(incidentKey) : Promise.resolve(null)), [incidentKey]);
  const branches = data ? Object.entries(data.branches).sort((a, b) => b[1] - a[1]) : [];

  return (
    <Drawer open={Boolean(incidentKey)} onClose={onClose} eyebrow={incidentKey} title={data ? `${data.topic} outage` : 'Outage'} width={480}>
      <div className="scroll" style={{ padding: '4px 24px 24px', display: 'flex', flexDirection: 'column', gap: 22, flex: 1 }}>
        {loading && <div className="skeleton" style={{ height: 120 }} />}
        {error && <p className="error-box">{error.message}</p>}
        {data && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              <ActivityRings size={110} stroke={10} trackOpacity={colors.track} label="Outage rings"
                rings={[{ value: data.pulse.spread, color: colors.red }, { value: data.pulse.sameCause, color: colors.amber }, { value: Math.min(1, data.pulse.minutesOpen / data.pulse.responseTargetMin), color: colors.blue }]} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: 28, fontWeight: 800 }}>{data.count} reports</span>
                <span className="muted" style={{ fontSize: 13 }}>{data.pulse.spread.toFixed(1)}x the outage level · open {data.pulse.minutesOpen} min</span>
                <span className="muted" style={{ fontSize: 13 }}>{Object.entries(data.languages).map(([l, n]) => `${n} ${l.toUpperCase()}`).join(' · ')}</span>
              </div>
            </div>

            <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <span className="eyebrow">Branches affected</span>
              {branches.map(([name, n]) => (
                <div key={name} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 24px', alignItems: 'center', gap: 10, fontSize: 13 }}>
                  <span>{name}</span><ConfidenceBar value={(n / branches[0][1]) * 100} /><span className="mono muted">{n}</span>
                </div>
              ))}
            </section>

            <section style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span className="eyebrow">Similar tickets</span>
              <ul className="list">
                {data.tickets.map((t) => (
                  <li key={t.ticketId}>
                    <button className="row-hover" onClick={() => onOpenTicket(t.ticketId)}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px 8px', border: 0, borderRadius: 10, background: 'transparent', textAlign: 'left' }}>
                      <Dot tone={t.severity} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.subject || t.bodyPreview}</span>
                        <span className="muted" style={{ fontSize: 11 }}>{t.ticketId} · {t.branch} · {t.language.toUpperCase()}</span>
                      </span>
                      <span className="faint" style={{ fontSize: 11 }}>{timeAgo(t.receivedAt)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </Drawer>
  );
}
