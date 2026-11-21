import { ActivityRings } from '../../components/ui/ActivityRings.jsx';
import { useTheme } from '../../theme/ThemeContext.jsx';

/** Three rings that each answer one operator question about a live outage. */
export function OutagePulse({ incident, onTrack }) {
  const { colors } = useTheme();
  const p = incident.pulse;
  const left = Math.max(0, p.responseTargetMin - p.minutesOpen);
  const rings = [
    { value: p.spread, color: colors.red, name: 'Spread', value_: String(incident.count), sub: `${p.spread.toFixed(1)}x outage level` },
    { value: p.sameCause, color: colors.amber, name: 'Same cause', value_: `${Math.round(p.sameCause * 100)}%`, sub: 'reports alike' },
    { value: Math.min(1, p.minutesOpen / p.responseTargetMin), color: colors.blue, name: 'Time left', value_: `${left} min`, sub: `of ${p.responseTargetMin} to respond` },
  ];
  return (
    <section aria-label="Outage pulse" className="glass card rise" style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 30, animationDelay: '.08s' }}>
      <ActivityRings rings={rings} trackOpacity={colors.track} label="Outage rings: spread, same cause, time left" />
      <div style={{ flex: '1 1 300px', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 18 }}>
        {rings.map((r) => (
          <div key={r.name} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: r.color, textTransform: 'uppercase' }}>{r.name}</span>
            <span style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em' }}>{r.value_}</span>
            <span className="muted" style={{ fontSize: 12 }}>{r.sub}</span>
          </div>
        ))}
      </div>
      <button className="btn-link" onClick={onTrack}>Track all {incident.count} reports →</button>
    </section>
  );
}
