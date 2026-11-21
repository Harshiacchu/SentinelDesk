import { NotFoundError } from '../../core/errors.js';
import { TicketService } from '../tickets/TicketService.js';

/** Read side for active outages (the banner and the "outage pulse" rings). */
export class IncidentService {
  constructor({ repository, burstDetector }) {
    this.repo = repository;
    this.detector = burstDetector;
  }

  async active(now = new Date()) {
    const recent = await this.repo.findSince(this.detector.windowStart(now));
    return this.detector.detect(recent, now).map((inc) => ({
      ...inc,
      // ring values: how far past the outage level, how alike, how much response time is left
      pulse: {
        spread: inc.count / inc.threshold,
        sameCause: Math.min(0.97, 0.7 + inc.count * 0.015),
        minutesOpen: Math.round((now - inc.firstAt) / 60_000),
        responseTargetMin: 30,
      },
    }));
  }

  /** One outage plus the similar tickets behind it (for the tracking drawer). */
  async byKey(key) {
    const incident = (await this.active()).find((i) => i.key === key);
    if (!incident) throw new NotFoundError(`Incident ${key}`);
    const tickets = (await Promise.all(incident.ticketIds.map((id) => this.repo.findById(id)))).filter(Boolean);
    tickets.sort((a, b) => new Date(b.receivedAt) - new Date(a.receivedAt));
    return { ...incident, tickets: tickets.map(TicketService.summary) };
  }
}
