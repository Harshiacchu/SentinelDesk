/** Shared vocabulary. Values match sentineldesk/contracts.py so both stacks speak the same language. */
export const TicketTypes = Object.freeze(['Incident', 'Request', 'Problem', 'Change']);
export const Priorities = Object.freeze(['high', 'medium', 'low']);
export const Languages = Object.freeze(['en', 'de']);

/** The 10 gate checks from the team plan (gate.pre then gate.post). */
export const GateChecks = Object.freeze([
  'INJECTION', 'HIGH_INCIDENT', 'RISKY_ASK', 'LOW_CONFIDENCE', 'NO_PRECEDENT',
  'NOT_FOUND', 'BAD_CITATION', 'UNSUPPORTED_NUMBER', 'LANG_MISMATCH', 'REFUSAL',
]);

export const TicketStatus = Object.freeze({ OPEN: 'open', SENT: 'sent', ESCALATED: 'escalated', RESOLVED: 'resolved' });
