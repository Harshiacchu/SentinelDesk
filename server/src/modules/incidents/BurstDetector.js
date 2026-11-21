/**
 * Finds outages: several similar incidents (same topic) inside a short window.
 * Pure logic, no I/O, so it is trivial to test and to swap for embedding clustering.
 */
export class BurstDetector {
  constructor({ windowMin, minTickets }) {
    this.windowMs = windowMin * 60_000;
    this.minTickets = minTickets;
  }

  windowStart(now = new Date()) {
    return new Date(now.getTime() - this.windowMs);
  }

  /** @returns {Array<{key, topic, count, branches, ticketIds, firstAt, lastAt}>} sorted by size */
  detect(tickets, now = new Date()) {
    const since = this.windowStart(now);
    const groups = new Map();
    for (const t of tickets) {
      if (t.triage?.type?.label !== 'Incident' || t.topic === 'Other' || new Date(t.receivedAt) < since) continue;
      const g = groups.get(t.topic) ?? { key: `INC-${t.topic.toUpperCase()}`, topic: t.topic, tickets: [] };
      g.tickets.push(t);
      groups.set(t.topic, g);
    }
    return [...groups.values()]
      .filter((g) => g.tickets.length >= this.minTickets)
      .map(({ key, topic, tickets: list }) => {
        const times = list.map((t) => new Date(t.receivedAt).getTime());
        const branches = {};
        for (const t of list) branches[t.branch] = (branches[t.branch] ?? 0) + 1;
        const languages = {};
        for (const t of list) languages[t.language] = (languages[t.language] ?? 0) + 1;
        return {
          key, topic, count: list.length, branches, languages,
          ticketIds: list.map((t) => t.ticketId),
          firstAt: new Date(Math.min(...times)), lastAt: new Date(Math.max(...times)),
          threshold: this.minTickets,
          windowMin: this.windowMs / 60_000,
        };
      })
      .sort((a, b) => b.count - a.count);
  }
}
