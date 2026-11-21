import { request } from './http.js';

/** Every backend call in one typed-by-convention module, grouped by resource. */
export const api = {
  meta: () => request('/meta'),

  triage: (ticket) => request('/triage', { method: 'POST', body: ticket }),

  tickets: {
    list: ({ filter = 'needs', page = 1, limit = 8 } = {}) => request(`/tickets?filter=${filter}&page=${page}&limit=${limit}`),
    get: (id) => request(`/tickets/${encodeURIComponent(id)}`),
    feedback: (id, verdict) => request(`/tickets/${encodeURIComponent(id)}/feedback`, { method: 'POST', body: { verdict } }),
    note: (id, text) => request(`/tickets/${encodeURIComponent(id)}/notes`, { method: 'POST', body: { text } }),
    act: (id, action) => request(`/tickets/${encodeURIComponent(id)}/actions`, { method: 'POST', body: { action } }),
    chat: (id, question) => request(`/tickets/${encodeURIComponent(id)}/chat`, { method: 'POST', body: { question } }),
  },

  incidents: {
    active: () => request('/incidents/active'),
    get: (key) => request(`/incidents/${encodeURIComponent(key)}`),
  },

  agent: {
    queue: ({ view = 'unclaimed', agent = '', page = 1, limit = 8 } = {}) => request(`/agent/queue?view=${view}&agent=${encodeURIComponent(agent)}&page=${page}&limit=${limit}`),
    assist: (id) => request(`/agent/tickets/${encodeURIComponent(id)}/assist`),
    claim: (id, agent) => request(`/agent/tickets/${encodeURIComponent(id)}/claim`, { method: 'POST', body: { agent } }),
    release: (id, agent) => request(`/agent/tickets/${encodeURIComponent(id)}/release`, { method: 'POST', body: { agent } }),
    message: (id, agent, text) => request(`/agent/tickets/${encodeURIComponent(id)}/messages`, { method: 'POST', body: { agent, text } }),
    resolve: (id, agent) => request(`/agent/tickets/${encodeURIComponent(id)}/resolve`, { method: 'POST', body: { agent } }),
  },

  support: {
    open: (ticket) => request('/support/tickets', { method: 'POST', body: ticket }),
    view: (id, key) => request(`/support/tickets/${encodeURIComponent(id)}?key=${encodeURIComponent(key)}`),
    say: (id, key, text) => request(`/support/tickets/${encodeURIComponent(id)}/messages?key=${encodeURIComponent(key)}`, { method: 'POST', body: { text } }),
    person: (id, key) => request(`/support/tickets/${encodeURIComponent(id)}/person?key=${encodeURIComponent(key)}`, { method: 'POST' }),
    eventsUrl: (id, key) => `/api/support/tickets/${encodeURIComponent(id)}/events?key=${encodeURIComponent(key)}`,
  },

  analytics: {
    overview: (hours = 6) => request(`/analytics/overview?hours=${hours}`),
    heatmap: (minutes = 60) => request(`/analytics/heatmap?minutes=${minutes}`),
  },
};
