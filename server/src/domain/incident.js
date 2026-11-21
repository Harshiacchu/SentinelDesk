/**
 * Does this ticket count as an incident for outage detection?
 * Either the classifier says Incident, or the gate flagged it as a high-priority incident
 * (severity words such as "Ausfall" or "outage" can do that even when the type head disagrees).
 */
export const isIncidentLike = (t) => t.triage?.type?.label === 'Incident' || (t.reasons ?? []).includes('HIGH_INCIDENT');
