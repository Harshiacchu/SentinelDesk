/** Pure: what changed between two triage results, in words an IT person reads at a glance. */
const FIELDS = [
  ['Decision', (t) => t.headline],
  ['Type', (t) => t.triage?.type?.label],
  ['Department', (t) => t.triage?.queue?.label],
  ['Priority', (t) => t.triage?.priority?.label],
  ['Problem type', (t) => t.topic],
  ['Outage', (t) => (t.incidentKey ? `part of ${t.incidentKey}` : 'none')],
];

export function describeChanges(before, after) {
  const changes = FIELDS
    .map(([label, get]) => ({ label, from: get(before) ?? '—', to: get(after) ?? '—' }))
    .filter((c) => c.from !== c.to);
  const added = (after.reasons ?? []).filter((r) => !(before.reasons ?? []).includes(r));
  const removed = (before.reasons ?? []).filter((r) => !(after.reasons ?? []).includes(r));
  if (added.length) changes.push({ label: 'New reasons', from: '—', to: added.join(', ') });
  if (removed.length) changes.push({ label: 'Cleared reasons', from: removed.join(', '), to: '—' });
  return changes;
}
