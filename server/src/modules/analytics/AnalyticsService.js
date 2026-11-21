import { BranchSites, Branches } from '../../domain/constants.js';

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

    const count = (key) => tickets.reduce((m, t) => ((m[key(t)] = (m[key(t)] ?? 0) + 1), m), {});
    const latencies = tickets.map(totalMs).sort((a, b) => a - b);
    const feedback = tickets.flatMap((t) => t.feedback ?? []);
    const right = feedback.filter((f) => f.verdict === 'right').length;

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
      severity: count((t) => t.severity),
      queues: Object.entries(count((t) => t.triage.queue.label)).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value),
      languages: count((t) => t.language),
      reasons: Object.entries(tickets.flatMap((t) => t.reasons).reduce((m, r) => ((m[r] = (m[r] ?? 0) + 1), m), {}))
        .map(([code, value]) => ({ code, value })).sort((a, b) => b.value - a.value),
    };
  }

  /** Branch x topic grid of incidents in the last N minutes. Hot cells = possible outage at that site. */
  async heatmap({ minutes = 60, now = new Date() } = {}) {
    const since = new Date(now - minutes * 60_000);
    const incidents = (await this.repo.findSince(since)).filter((t) => t.triage.type.label === 'Incident');
    const topics = this.topics.topics.filter((t) => t !== 'Other');
    const cells = {};
    for (const t of incidents) {
      if (!topics.includes(t.topic)) continue;
      const k = `${t.branch}|${t.topic}`;
      cells[k] = (cells[k] ?? 0) + 1;
    }
    const max = Math.max(1, ...Object.values(cells));
    const sites = BranchSites.map((site) => {
      const own = incidents.filter((t) => t.branch === site.name);
      const byTopic = topics.map((topic) => ({ topic, value: cells[`${site.name}|${topic}`] ?? 0 })).sort((a, b) => b.value - a.value);
      return { ...site, incidents: own.length, top: byTopic[0].value ? byTopic[0] : null, hot: byTopic[0].value >= this.detector.minTickets };
    });
    return {
      sites,
      minutes,
      branches: Branches,
      topics,
      max,
      hotThreshold: this.detector.minTickets,
      cells: Branches.flatMap((branch) => topics.map((topic) => {
        const value = cells[`${branch}|${topic}`] ?? 0;
        return { branch, topic, value, hot: value >= this.detector.minTickets };
      })),
    };
  }
}
