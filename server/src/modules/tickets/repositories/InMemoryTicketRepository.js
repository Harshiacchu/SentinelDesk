import { ListRules, TicketRepository } from './TicketRepository.js';

/** Zero-setup store for demos and local dev. Resets on restart. */
export class InMemoryTicketRepository extends TicketRepository {
  #byId = new Map();

  async save(record) {
    this.#byId.set(record.ticketId, structuredClone(record));
    return record;
  }

  async findById(id) {
    const r = this.#byId.get(id);
    return r ? structuredClone(r) : null;
  }

  async update(id, patch) {
    const current = this.#byId.get(id);
    if (!current) return null;
    Object.assign(current, patch);
    return structuredClone(current);
  }

  async append(id, field, entry) {
    const current = this.#byId.get(id);
    if (!current) return null;
    current[field] = [...(current[field] ?? []), entry];
    return structuredClone(current);
  }

  async list({ filter = 'all', page = 1, limit = 8, agent }) {
    const all = [...this.#byId.values()].filter((r) => ListRules.matches(r, filter, { agent })).sort(ListRules.compare(filter));
    return { items: all.slice((page - 1) * limit, page * limit).map((r) => structuredClone(r)), total: all.length };
  }

  async findSince(date) {
    return [...this.#byId.values()].filter((r) => new Date(r.receivedAt) >= date).map((r) => structuredClone(r));
  }

  async count() {
    return this.#byId.size;
  }
}
