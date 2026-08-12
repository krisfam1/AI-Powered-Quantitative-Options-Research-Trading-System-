import app from "./app";
import { logger } from "./lib/logger";
import { shutdownTradingLoop, startTradingLoop } from "./lib/trader";

const rawPort = process.env["PORT"];

if (!rawPort) {
  throw new Error(
    "PORT environment variable is required but was not provided.",
  );
}

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

app.listen(port, (err) => {
  if (err) {
    logger.error({ err }, "Error listening on port");
    process.exit(1);
  }

  logger.info({ port }, "Server listening");

  // In production (TRADING_LOOP=1) the API server supervises the Python
  // trading loop, since artifact-mode deployments only start this server.
  startTradingLoop();
});

let shuttingDown = false;
for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.on(signal, () => {
    if (shuttingDown) return;
    shuttingDown = true;
    logger.info({ signal }, "shutting down — stopping trading loop");
    void shutdownTradingLoop().finally(() => process.exit(0));
  });
}
