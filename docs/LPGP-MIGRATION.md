# LPGP migration plan

**Product:** LPGP (LightingPlays Game Panel)  
**Brand credit:** Made by LightingPlays
**Brand palette:** Sky blue primary with warm yellow accents on a dark interface  
**Distribution goal:** Free panel software; no paid licence, activation code, or licence-server dependency.

## Architecture decision

Use the JTG Panel interface and interaction patterns as the visual reference, while keeping LPGP's existing runtime:
- React + Vite frontend
- FastAPI backend
- PostgreSQL / SQLAlchemy / Alembic
- Docker-based Minecraft runtime
- Existing VPS node-agent and task queue

Do not replace the backend with JTG's Express/JSON storage stack. The two backends have different data models and runtime contracts; replacing them would risk existing accounts, server records, node enrollment, and persistent volumes.

## Non-negotiable access model

- No product licence key, activation code, paid entitlement check, or external licence server.
- Keep normal account sign-in and role-based authorization. A free panel still needs authenticated users.
- Keep per-node enrollment credentials and API/session tokens where they protect node-to-panel communication. These are security credentials, not product licence keys.
- Keep server ownership checks and customer isolation. Never make server consoles, files, backups, or node administration public.
- Stripe billing in the current code is an optional hosting-operator/customer billing integration; it must never be used to activate or restrict LPGP itself.

## Migration phases

1. **Brand and foundation** — rename visible product identity to LPGP, add LightingPlays credit, establish the LPGP sky-blue and yellow visual identity, using JTG's layout as the reference. (Started on this branch.)
2. **Interface migration** — in progress. The current branch now has a JTG-inspired collapsible navigation shell, grouped navigation, a deploy-server entry, fleet summary cards, a responsive server-card grid, and the existing API-backed server workspace (console, file manager, Minecraft controls, backups, and per-server team access). Remaining work: account/admin page parity, richer server metrics, global search/notifications, and additional JTG workflows that have compatible LPGP API support.
3. **Feature parity** — bring over useful JTG workflows (server console, file manager, backups, plugins/mods, SFTP where safely implemented, API-key management, sub-users, and system settings) through compatible FastAPI endpoints or new tested endpoints.
4. **Free distribution** — verify there is no product activation/licence enforcement; document installation and update paths; keep optional host billing separate from panel licensing.
5. **Release hardening** — run frontend builds, backend tests, migrations, node-agent integration tests, authorization tests, backup/restore tests, and a clean install on a disposable VPS before public release.

## Current cautions

- LPGP's README describes the current runtime as an early single-node foundation, not a production-hardened multi-tenant hosting panel.
- Do not advertise SFTP, plugin/mod management, or other JTG functions as implemented in LPGP until they have working backend support and tests.
- Keep the original database schema and persistent Docker volume paths stable during migration.
- JTG files have their own license headers/metadata. Reuse the design direction first; carry over source files only after confirming and preserving their applicable license notices.
