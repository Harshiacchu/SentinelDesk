import mongoose from 'mongoose';
import { TicketRepository } from './TicketRepository.js';
import { TicketModel } from '../ticket.model.js';
import { createLogger } from '../../../core/logger.js';

const log = createLogger('mongo');
const PROJECTION = { _id: 0 };

const FILTERS = {
  needs: { status: { $nin: ['sent', 'resolved'] }, severity: { $ne: 'ready' } },
  ready: { status: { $nin: ['sent', 'resolved'] }, severity: 'ready' },
  done: { status: { $in: ['sent', 'resolved'] } },
  all: {},
};

export class MongoTicketRepository extends TicketRepository {
  constructor({ uri }) {
    super();
    if (!uri) throw new Error('MONGODB_URI is required when TICKET_STORE=mongo');
    this.uri = uri;
  }

  async connect() {
    await mongoose.connect(this.uri, { serverSelectionTimeoutMS: 5000 });
    log.info('connected');
  }

  async save(record) {
    await TicketModel.create(record);
    return record;
  }

  async findById(id) {
    return TicketModel.findOne({ ticketId: id }, PROJECTION).lean();
  }

  async update(id, patch) {
    return TicketModel.findOneAndUpdate({ ticketId: id }, { $set: patch }, { new: true, projection: PROJECTION }).lean();
  }

  async append(id, field, entry) {
    return TicketModel.findOneAndUpdate({ ticketId: id }, { $push: { [field]: entry } }, { new: true, projection: PROJECTION }).lean();
  }

  async list({ filter = 'all', page = 1, limit = 8 }) {
    const query = FILTERS[filter] ?? {};
    const sort = filter === 'done' ? { receivedAt: -1 } : { severityRank: 1, receivedAt: -1 };
    const [items, total] = await Promise.all([
      TicketModel.find(query, PROJECTION).sort(sort).skip((page - 1) * limit).limit(limit).lean(),
      TicketModel.countDocuments(query),
    ]);
    return { items, total };
  }

  async findSince(date) {
    return TicketModel.find({ receivedAt: { $gte: date } }, PROJECTION).lean();
  }

  async count() {
    return TicketModel.estimatedDocumentCount();
  }
}
