import { NotImplementedError } from '../../../core/errors.js';

/**
 * Port: persistence for live tickets (never the holdout split).
 * Filters: 'needs' (a person must act) | 'ready' (safe to send) | 'done' | 'all'
 * @abstract
 */
export class TicketRepository {
  async connect() {}
  async save(_record) { throw new NotImplementedError(this.constructor.name, 'save'); }
  async findById(_id) { throw new NotImplementedError(this.constructor.name, 'findById'); }
  async update(_id, _patch) { throw new NotImplementedError(this.constructor.name, 'update'); }
  async append(_id, _field, _entry) { throw new NotImplementedError(this.constructor.name, 'append'); }
  async list(_query) { throw new NotImplementedError(this.constructor.name, 'list'); }
  async findSince(_date) { throw new NotImplementedError(this.constructor.name, 'findSince'); }
  async count() { throw new NotImplementedError(this.constructor.name, 'count'); }
}

/** Shared filter + sort rules so both implementations behave identically. */
export const ListRules = {
  matches(record, filter, { agent } = {}) {
    const done = record.status === 'sent' || record.status === 'resolved';
    const forAgent = record.severity !== 'ready' || record.status === 'escalated' || record.status === 'in_progress';
    switch (filter) {
      case 'unclaimed': return !done && forAgent && !record.assignee;
      case 'mine': return !done && record.assignee === agent;
      case 'resolved_by_agents': return done && Boolean(record.assignee);
      case 'needs': return !done && record.severity !== 'ready';
      case 'ready': return !done && record.severity === 'ready';
      case 'done': return done;
      default: return true;
    }
  },
  compare(filter) {
    return filter === 'done' || filter === 'resolved_by_agents'
      ? (a, b) => new Date(b.receivedAt) - new Date(a.receivedAt)
      : (a, b) => a.severityRank - b.severityRank || new Date(b.receivedAt) - new Date(a.receivedAt);
  },
};
