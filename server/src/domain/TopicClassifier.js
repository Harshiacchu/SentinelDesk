/**
 * Groups tickets by the system they talk about, so similar reports can be clustered
 * into one incident and plotted on the branch heatmap.
 * Keyword based on purpose: cheap, explainable, works in EN + DE.
 * Swap for embedding clusters later without touching callers.
 */
const TOPICS = [
  ['VPN', /\bvpn\b|remote access|fernzugriff/i],
  ['Login', /log ?in|sign ?in|password|passwort|kennwort|sso|anmeld/i],
  ['Email', /e-?mail|outlook|exchange|postfach/i],
  ['Printer', /printer|drucker|print/i],
  ['Network', /network|netzwerk|internet|wi-?fi|wlan|offline/i],
  ['Billing', /invoice|refund|billing|rechnung|erstattung|payment|zahlung|charge/i],
  ['Database', /database|datenbank|sql|server down/i],
];

export class TopicClassifier {
  classify(text) {
    const hit = TOPICS.find(([, re]) => re.test(text));
    return hit ? hit[0] : 'Other';
  }

  get topics() {
    return [...TOPICS.map(([t]) => t), 'Other'];
  }
}
