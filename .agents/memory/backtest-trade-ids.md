---
name: Backtest trade IDs
description: Rerun behavior for simulated trades stored in SQLite
---

Backtest trade IDs are derived from the ticker and entry-bar timestamp, making repeated runs of the same historical window idempotent.

**Why:** A script that runs from the project workflow may execute repeatedly; duplicate simulated entries would distort trade counts and performance summaries.

**How to apply:** Preserve deterministic IDs when changing backtest logic, or intentionally version the ID scheme if a new strategy definition must coexist with prior results.