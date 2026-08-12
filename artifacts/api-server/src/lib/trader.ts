import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { logger } from "./logger";

/**
 * Supervises the Python trading loop as a child process.
 *
 * In production the deployment platform runs this API server (artifact mode),
 * so the server is responsible for starting `python main.py` when
 * TRADING_LOOP=1. The Python kill-switch control panel binds to
 * KILL_SERVER_PORT (8081) and is proxied by this server at /status, /stop
 * and /resume.
 */

export const KILL_SERVER_PORT = 8081;

let child: ChildProcess | null = null;
let stopped = false;
let restartDelayMs = 5_000;
let restartTimer: NodeJS.Timeout | null = null;
let startedAt = 0;
const MAX_RESTART_DELAY_MS = 5 * 60_000;
const HEALTHY_RUNTIME_MS = 60_000;

function workspaceRoot(): string {
  // The bundled server lives at <root>/artifacts/api-server/dist/index.mjs;
  // main.py lives at the workspace root. Walk up from this module until we
  // find it, falling back to cwd.
  let dir = path.dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 6; i++) {
    if (existsSync(path.join(dir, "main.py"))) return dir;
    dir = path.dirname(dir);
  }
  return process.cwd();
}

function launch(): void {
  if (stopped) return;

  child = spawn("python", ["main.py"], {
    cwd: workspaceRoot(),
    env: {
      ...process.env,
      TRADING_LOOP: "1",
      KILL_SERVER_PORT: String(KILL_SERVER_PORT),
      PYTHONUNBUFFERED: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  startedAt = Date.now();
  logger.info({ pid: child.pid }, "trading loop started (python main.py)");

  child.on("error", (err) => {
    logger.error({ err }, "failed to spawn trading loop");
  });

  child.stdout?.on("data", (chunk: Buffer) => {
    for (const line of chunk.toString().split("\n")) {
      if (line.trim()) logger.info({ trader: true }, line);
    }
  });
  child.stderr?.on("data", (chunk: Buffer) => {
    for (const line of chunk.toString().split("\n")) {
      if (line.trim()) logger.warn({ trader: true }, line);
    }
  });

  child.on("exit", (code, signal) => {
    logger.warn({ code, signal }, "trading loop exited");
    child = null;
    if (stopped) return;
    // Clean end-of-day exit (code 0) or crash: restart after a delay.
    // The loop itself handles market-hours gating, so restarting at any
    // time is safe — it will just wait for the next market open.
    const ranHealthy = Date.now() - startedAt >= HEALTHY_RUNTIME_MS;
    if (code === 0 || ranHealthy) {
      restartDelayMs = 5_000;
    }
    const delay = code === 0 ? 60_000 : restartDelayMs;
    if (code !== 0 && !ranHealthy) {
      restartDelayMs = Math.min(restartDelayMs * 2, MAX_RESTART_DELAY_MS);
    }
    logger.info({ delayMs: delay }, "restarting trading loop");
    restartTimer = setTimeout(launch, delay);
    restartTimer.unref();
  });
}

export function startTradingLoop(): void {
  if (process.env["TRADING_LOOP"] !== "1") {
    logger.info("TRADING_LOOP is not set to 1 — trading loop not started");
    return;
  }
  stopped = false;
  launch();
}

export function stopTradingLoop(): void {
  stopped = true;
  if (restartTimer) {
    clearTimeout(restartTimer);
    restartTimer = null;
  }
  if (child) child.kill("SIGTERM");
}

/**
 * Graceful shutdown: stop supervising, SIGTERM the child, and give it a
 * bounded window to exit before SIGKILL. Called from process signal handlers
 * so a deployment replacement never orphans or duplicates the Python loop.
 */
export async function shutdownTradingLoop(timeoutMs = 8_000): Promise<void> {
  stopped = true;
  if (restartTimer) {
    clearTimeout(restartTimer);
    restartTimer = null;
  }
  const c = child;
  if (!c) return;
  await new Promise<void>((resolve) => {
    const killTimer = setTimeout(() => {
      c.kill("SIGKILL");
    }, timeoutMs);
    killTimer.unref();
    c.once("exit", () => {
      clearTimeout(killTimer);
      resolve();
    });
    c.kill("SIGTERM");
  });
}
