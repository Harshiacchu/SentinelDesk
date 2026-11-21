import { Icon } from '../../components/ui/Icon.jsx';
import { Dot } from '../../components/ui/Tone.jsx';

const branchList = (branches) => {
  const names = Object.entries(branches).sort((a, b) => b[1] - a[1]).map(([n]) => n);
  return names.length > 3 ? `${names.slice(0, 3).join(', ')} +${names.length - 3}` : names.join(', ');
};

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
              {branchList(inc.branches)} · in the last {Math.max(1, inc.pulse.minutesOpen)} min · outage level is {inc.threshold}
            </span>
          </div>
          <button className="btn press" onClick={() => onTrack(inc.key)}>Track similar tickets</button>
        </div>
      ))}
    </div>
  );
}
