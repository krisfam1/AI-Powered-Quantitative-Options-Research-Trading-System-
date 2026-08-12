---
name: Artifact-mode deployment overrides .replit run
description: Publishing this multi-artifact project starts only the registered artifacts, not the .replit [deployment] run command.
---

**Rule:** Because this project has registered artifacts (api-server, mockup-sandbox), published deployments run in "artifact mode": the platform starts the api-server artifact bundle (`node artifacts/api-server/dist/index.mjs` on PORT) and completely ignores `[deployment] run = python main.py` in `.replit`. There is no callback to unregister an artifact.

**Why:** First VM publish (Aug 2026) came up with only the Node API server; the Python trading loop never started and this was only visible in deployment logs ("artifact mode enabled").

**How to apply:** Anything that must run in production has to be launched by the api-server process. The api-server supervises `python main.py` (spawn with TRADING_LOOP=1, KILL_SERVER_PORT=8081, restart with backoff, SIGTERM teardown) and proxies GET /status,/stop,/resume to the Python kill-switch server on 127.0.0.1:8081. In dev, `python main.py` single-pass mode is unchanged and the kill server defaults to port 8080.
