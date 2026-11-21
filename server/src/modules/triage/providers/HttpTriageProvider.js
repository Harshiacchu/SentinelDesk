import { TriageProvider } from './TriageProvider.js';
import { UpstreamError } from '../../../core/errors.js';
import { ticketText } from '../../../domain/ticketText.js';

/** REAL provider: POSTs the ticket to the Python pipeline service and maps its answer. */
export class HttpTriageProvider extends TriageProvider {
  constructor({ url, mapper, timeoutMs = 20_000 }) {
    super();
    this.url = url;
    this.mapper = mapper;
    this.timeoutMs = timeoutMs;
  }

  async analyze(ticket) {
    let res;
    try {
      res = await fetch(this.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject: ticket.subject ?? null, body: ticket.body }),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (err) {
      throw new UpstreamError('pipeline', err);
    }
    if (!res.ok) throw new UpstreamError('pipeline', `HTTP ${res.status}`);
    return this.mapper.toTriageResult(await res.json(), ticketText(ticket));
  }
}
