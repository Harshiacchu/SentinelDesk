import { request } from './http.js';

/** Every backend call in one typed-by-convention module, grouped by resource. */
export const api = {
  meta: () => request('/meta'),

  translate: (text, target, source) => request('/translate', { method: 'POST', body: { text, target, source } }),

  triage: (ticket) => request('/triage', { method: 'POST', body: ticket }),

  tickets: {
    list: ({ filter = 'needs', page = 1, limit = 8 } = {}) => request(`/tickets?filter=${filter}&page=${page}&limit=${limit}`),
    get: (id) => request(`/tickets/${encodeURIComponent(id)}`),
    feedback: (id, verdict) => request(`/tickets/${encodeURIComponent(id)}/feedback`, { method: 'POST', body: { verdict } }),
    note: (id, text) => request(`/tickets/${encodeURIComponent(id)}/notes`, { method: 'POST', body: { text } }),
    followUp: (id, text) => request(`/tickets/${encodeURIComponent(id)}/followups`, { method: 'POST', body: { text } }),
    editDraft: (id, text) => request(`/tickets/${encodeURIComponent(id)}/draft`, { method: 'PUT', body: { text } }),
    act: (id, action) => request(`/tickets/${encodeURIComponent(id)}/actions`, { method: 'POST', body: { action } }),
  },

  incidents: {
    active: () => request('/incidents/active'),
    get: (key) => request(`/incidents/${encodeURIComponent(key)}`),
  },

  analytics: {
    overview: (hours = 6) => request(`/analytics/overview?hours=${hours}`),
    heatmap: (hours = 6) => request(`/analytics/heatmap?hours=${hours}`),
  },
};
