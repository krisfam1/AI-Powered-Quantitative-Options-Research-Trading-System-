---
name: Validated Replit config
description: Replit-specific constraint for changing the project run configuration
---

Changes to `.replit` are schema-validated through the dedicated replacement flow; direct patching can be rejected even when the TOML is valid.

**Why:** This protects workspace run commands, workflows, and environment settings from malformed or conflicting configuration.

**How to apply:** Write the complete intended configuration to a temporary workspace file, then submit it through the validated replacement callback.