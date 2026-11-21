import { isIncidentLike } from '../../domain/incident.js';

const pct = (sorted, p) => (sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] : 0);
const totalMs = (t) => t.latency.reduce((a, s) => a + s.ms, 0);

/** Aggregates for the Insights page. Read-only, computed from recent tickets. */
export class AnalyticsService {
  constructor({ repository, topicClassifier, burstDetector }) {
    this.repo = repository;
    this.topics = topicClassifier;
    this.detector = burstDetector;
  }

  async overview({ hours = 6, bucketMin = 30, now = new Date() } = {}) {
    const since = new Date(now - hours * 3_600_000);
    const tickets = await this.repo.findSince(since);

    const buckets = [];
    for (let t = since.getTime(); t < now.getTime(); t += bucketMin * 60_000) {
      buckets.push({ start: new Date(t), critical: 0, review: 0, ready: 0 });
    }
    for (const t of tickets) {
      const i = Math.min(buckets.length - 1, Math.floor((new Date(t.receivedAt) - since) / (bucketMin * 60_000)));
      if (buckets[i]) buckets[i][t.severity] += 1;
    }

    const latencies = tickets.map(totalMs).sort((a, b) => a - b);
    const feedback = tickets.flatMap((t) => t.feedback ?? []);
    const right = feedback.filter((f) => f.verdict === 'right').length;
    const byTopic = tickets.reduce((m, t) => ((m[t.topic] = (m[t.topic] ?? 0) + 1), m), {});

    return {
      window: { hours, bucketMin },
      kpis: {
        total: tickets.length,
        escalated: tickets.filter((t) => t.severity !== 'ready').length,
        autoDrafted: tickets.filter((t) => t.severity === 'ready').length,
        p50Ms: pct(latencies, 0.5),
        p95Ms: pct(latencies, 0.95),
        agreement: feedback.length ? right / feedback.length : null,
        feedbackCount: feedback.length,
      },
      volume: buckets,
      severity: tickets.reduce((m, t) => ((m[t.severity] = (m[t.severity] ?? 0) + 1), m), {}),
      topics: Object.entries(byTopic).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value),
      reasons: Object.entries(tickets.flatMap((t) => t.reasons).reduce((m, r) => ((m[r] = (m[r] ?? 0) + 1), m), {}))
        .map(([code, value]) => ({ code, value })).sort((a, b) => b.value - a.value),
    };
  }

  /**
   * Problem type x hour grid of incidents. Hot cells = an hour where one kind of
   * problem hit the outage level, i.e. probably one outage behind many tickets.
   */
  async heatmap({ hours = 6, now = new Date() } = {}) {
    const start = new Date(now);
    start.setMinutes(0, 0, 0);
    start.setHours(start.getHours() - (hours - 1));
    const incidents = (await this.repo.findSince(start)).filter(isIncidentLike);
    const topics = this.topics.topics.filter((t) => t !== 'Other');
    const hot = this.detector.minTickets * 2; // per hour: twice the 15-minute outage level
    const slots = Array.from({ length: hours }, (_, i) => new Date(start.getTime() + i * 3_600_000));
    const cells = {};
    for (const t of incidents) {
      const slot = Math.floor((new Date(t.receivedAt) - start) / 3_600_000);
      if (slot < 0 || slot >= hours || !topics.includes(t.topic)) continue;
      const k = `${t.topic}|${slot}`;
      cells[k] = (cells[k] ?? 0) + 1;
    }
    return {
      hours: slots.map((d) => d.toISOString()),
      topics,
      max: Math.max(1, ...Object.values(cells)),
      hotThreshold: hot,
      cells: topics.flatMap((topic) => slots.map((_, slot) => {
        const value = cells[`${topic}|${slot}`] ?? 0;
        return { topic, slot, value, hot: value >= hot };
      })),
    };
  }
}
