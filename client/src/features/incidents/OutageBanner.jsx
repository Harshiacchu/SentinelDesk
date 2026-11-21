import { Icon } from '../../components/ui/Icon.jsx';
import { Dot } from '../../components/ui/Tone.jsx';

/** Live strip shown whenever similar incidents cluster into a possible outage. */
export function OutageBanner({ incidents, onTrack }) {
  if (!incidents?.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {incidents.slice(0, 2).map((inc) => (
        <div key={inc.key} role="status" className="glass tone-critical sweep rise"
          style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 14, padding: '12px 16px', borderRadius: 16, borderColor: 'color-mix(in srgb, var(--red) 40%, transparent)' }}>
          <span style={{ width: 34, height: 34, borderRadius: 10, background: 'var(--red-soft)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="alert" stroke="var(--red)" />
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0, flex: '1 1 300px' }}>
            <span style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Dot tone="critical" pulse /> Possible {inc.topic} outage · {inc.count} similar reports
            </span>
            <span className="muted" style={{ fontSize: 12 }}>
              {inc.count} people reported the same {inc.topic} problem in the last {Math.max(1, inc.pulse.minutesOpen)} min. Probably one outage.
            </span>
          </div>
          <button className="btn press" onClick={() => onTrack(inc.key)}>See all reports</button>
        </div>
      ))}
    </div>
  );
}
