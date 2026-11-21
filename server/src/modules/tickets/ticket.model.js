import mongoose from 'mongoose';

const { Mixed } = mongoose.Schema.Types;

/** Nested pipeline output is stored as-is (Mixed): it is read whole, never queried inside. */
const ticketSchema = new mongoose.Schema(
  {
    ticketId: { type: String, required: true, unique: true, index: true },
    receivedAt: { type: Date, required: true, index: true },
    subject: { type: String, default: null },
    body: { type: String, required: true },
    language: String,
    topic: { type: String, index: true },
    severity: { type: String, index: true },
    severityRank: Number,
    headline: String,
    status: { type: String, index: true },
    incidentKey: { type: String, default: null },
    reasonDetails: { type: Mixed, default: {} },
    pii: { type: Mixed, default: null },
    followups: { type: [Mixed], default: [] },
    lastChange: { type: Mixed, default: null },
    editedDraft: { type: Mixed, default: null },
    triage: Mixed,
    decision: String,
    reasons: [String],
    checks: Mixed,
    precedents: Mixed,
    draft: Mixed,
    latency: Mixed,
    feedback: { type: [Mixed], default: [] },
    notes: { type: [Mixed], default: [] },
    activity: { type: [Mixed], default: [] },
  },
  { versionKey: false },
);

export const TicketModel = mongoose.models.Ticket || mongoose.model('Ticket', ticketSchema);
