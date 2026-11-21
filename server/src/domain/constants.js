/** Shared vocabulary. Values match sentineldesk/contracts.py so both stacks speak the same language. */
export const TicketTypes = Object.freeze(['Incident', 'Request', 'Problem', 'Change']);
export const Priorities = Object.freeze(['high', 'medium', 'low']);
export const Languages = Object.freeze(['en', 'de']);

/** Offices with coordinates for the outage map (region groups the map panels). */
export const BranchSites = Object.freeze([
  { name: 'Boston', region: 'North America', lat: 42.36, lon: -71.06 },
  { name: 'New York', region: 'North America', lat: 40.71, lon: -74.01 },
  { name: 'Chicago', region: 'North America', lat: 41.88, lon: -87.63 },
  { name: 'London', region: 'Europe', lat: 51.51, lon: -0.13 },
  { name: 'Berlin', region: 'Europe', lat: 52.52, lon: 13.4 },
  { name: 'Munich', region: 'Europe', lat: 48.14, lon: 11.58 },
  { name: 'Hamburg', region: 'Europe', lat: 53.55, lon: 9.99 },
  { name: 'Frankfurt', region: 'Europe', lat: 50.11, lon: 8.68 },
]);

export const Branches = Object.freeze(BranchSites.map((b) => b.name));

/** The 10 gate checks from the team plan (gate.pre then gate.post). */
export const GateChecks = Object.freeze([
  'INJECTION', 'HIGH_INCIDENT', 'RISKY_ASK', 'LOW_CONFIDENCE', 'NO_PRECEDENT',
  'NOT_FOUND', 'BAD_CITATION', 'UNSUPPORTED_NUMBER', 'LANG_MISMATCH', 'REFUSAL',
]);

export const TicketStatus = Object.freeze({ OPEN: 'open', SENT: 'sent', ESCALATED: 'escalated', RESOLVED: 'resolved' });
