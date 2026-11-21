import { buildContainer } from './container.js';
import { createApp } from './app.js';
import { createLogger } from './core/logger.js';

const log = createLogger('server');

async function main() {
  const c = buildContainer();
  await c.repository.connect();
  const existing = await c.repository.count();
  c.factory.startAfter(existing);
  if (c.config.seedDemo && existing === 0) await c.seeder.seed();

  createApp(c).listen(c.config.port, () => log.info(`SentinelDesk API on http://localhost:${c.config.port}`));
}

main().catch((err) => {
  log.error(err);
  process.exit(1);
});
