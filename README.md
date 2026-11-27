# LPGP — LightingPlays Game Panel

LPGP (LightingPlays Game Panel) is a free game-server management panel made by LightingPlays. The interface migration uses JTG Panel as its visual reference while retaining LPGP's FastAPI, PostgreSQL, Docker and VPS node-agent runtime. LPGP does not require a paid product licence, activation code, or licence-server connection.

**Made by LightingPlays. Free panel software for everyone.**

See [the LPGP migration plan](docs/LPGP-MIGRATION.md) for architecture decisions and release phases.

## Implemented foundations

- Responsive React/Vite panel with animated dark UI and protected sign-in.
- FastAPI backend with PostgreSQL, SQLAlchemy and Alembic migrations.
- Argon2 password hashing, short-lived JWT authentication, administrator roles, audit events, and authenticated password changes with current-password verification.
- VPS node enrollment, one-time node credentials and authenticated CPU/RAM/disk telemetry.
- Docker-backed Minecraft Java provisioning through the node agent.
- Persistent per-server Docker volumes, dedicated TCP allocations, CPU/RAM limits and queued start/stop/restart/delete operations.
- Node task leases for retrying interrupted work.
- GitHub Actions frontend build, backend tests and migration checks.

## Current runtime boundaries

The server inventory, deployment form, lifecycle controls, dashboard, node fleet, customer directory, audit log, billing view and operations metrics are connected to the FastAPI API. A connected Linux node with Docker Engine and the current agent can provision Minecraft Java (Paper) containers. Provisioning is asynchronous: the node pulls the Minecraft image and reports completion to the panel.

The server workspace includes:
- Minecraft console commands and short-polling container logs (not WebSocket streaming).
- A permission-checked browser file manager for list/read/write/create-folder/rename/delete and small uploads/downloads.
- Minecraft player/whitelist/operator actions and server.properties settings.
- Node-local create/list/restore backups and Minecraft version upgrades with pre-operation snapshots.
- Owner-managed server team access with API-enforced per-server permissions.
- Live node telemetry, administrative audit events, an activity-backed notification drawer, operational counters and optional Stripe customer billing.
- Authenticated account password changes and administrator-only node credential rotation with one-time token display.

This remains an early single-node runtime, not a production-hardened Pterodactyl replacement. Per-container CPU/RAM telemetry, automatic container health reconciliation, SFTP, plugin/mod installation, schedules, database provisioning, multi-allocation management, disk quotas, image update policy, firewall automation are not implemented. Node credentials can be rotated by an administrator; the new token is shown once and must be installed on the VPS agent before it reconnects. Stripe is optional hosting-customer billing and never activates LPGP itself. Do not expose this deployment to untrusted tenants until the remaining isolation and operational controls are implemented.

## Phase 6 — Console and file manager

The server workspace now includes an authenticated Minecraft command console, recent container log output, and a browser file manager. File operations are queued to the owning node agent and run only inside the server's `/data` volume. The web editor supports list/read/write/create-folder/rename/delete and upload/download for files up to 512 KiB. Paths are resolved against the server data directory to reject traversal outside the volume; symlink entries are not exposed.

Console log refresh uses short polling through the node task queue (not a WebSocket stream). The node agent must be updated and restarted on each VPS to execute the new `console`, `console_logs`, and `file_*` task types. SFTP credentials and a dedicated SFTP service are not implemented yet; use the browser file manager for small files and wait for the SFTP phase for large transfers.

## Requirements

- Node.js 22.12+ (or a supported current LTS)
- Python 3.11+
- Docker Engine and Docker Compose plugin for PostgreSQL
- Linux VPS for the node agent

## Frontend

```bash
npm install
cp .env.example .env
npm run dev
```

Set VITE_API_URL to the API origin (for example http://127.0.0.1:8000). The frontend calls /api/v1 itself.

## Backend

```bash
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit backend/.env. Set a unique SECRET_KEY with at least 32 random bytes and a strong POSTGRES_PASSWORD. Keep this file private.

Start PostgreSQL and API:

```bash
docker compose up -d db
alembic upgrade head
python scripts/create_admin.py --email admin@example.com --username admin
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

For containerized API deployment, use docker compose up -d --build from backend after configuring the environment. Put HTTPS termination and rate limiting in front of the API before public exposure.

## Enroll a VPS node

1. Authenticate as an administrator.
2. POST /api/v1/admin/nodes with JSON body {"name":"vps-01","fqdn":"node01.example.com"}.
3. Copy the returned one-time token securely.
4. Copy node-agent/ to the VPS and run sudo bash install.sh.
5. Enter the panel HTTPS URL and node token. The agent sends CPU, memory and disk telemetry every 15 seconds.

## Tests

```bash
cd backend
pip install -r requirements.txt
SECRET_KEY=local-test-secret-key-at-least-32-bytes DATABASE_URL=sqlite:///./test.db pytest -q
SECRET_KEY=local-test-secret-key-at-least-32-bytes DATABASE_URL=sqlite:///./migration.db alembic upgrade head
```

## Roadmap

1. Dashboard and responsive visual system — foundation present.
2. Authentication, roles and audit trail — implemented foundation.
3. API and database integration — implemented foundation.
4. VPS node enrollment and telemetry — implemented foundation.
5. Docker-backed Minecraft provisioning and lifecycle — implemented initial runtime.
6. Console and browser file manager — implemented; SFTP remains future work.
7. Minecraft controls, version upgrades and server.properties — initial implementation present.
8. Node-local backups — implemented; schedules, databases and allocations remain future work.
9. Customer ownership, subusers and per-server permissions — initial implementation present.
10. Optional Stripe billing, operational metrics, audit logs and baseline security controls — foundations present; production hardening remains.

The project should only mark a phase complete after its tests and end-to-end acceptance checks pass.


## Phase 8 — backups and version upgrades

- Admins can queue create/list/restore operations for per-server snapshots from the server workspace.
- The node agent stores compressed archives under `/var/lib/lighting-panel/backups/<server-id>`, outside the server data volume, with mode-0700 directories.
- Restore validates archive member paths and rejects symlinks, hardlinks, devices, and path traversal. A pre-restore snapshot is created before existing world data is replaced.
- Minecraft version upgrades use the fixed Paper image, validate release version syntax, create a pre-upgrade snapshot, and recreate the managed container while retaining its persistent named volume, port, and resource limits.
- Snapshots are node-local, capped at 20 GiB of uncompressed server data per snapshot, and are not off-site disaster recovery. Automated schedules and remote object storage are not included in this phase.
- Update and restart the node agent on every VPS before using backups or upgrades.

## Phase 9 — customer ownership and server team permissions

- Administrators can deploy a server for an existing active customer account by supplying that account's email as the optional owner email. Customers can see only servers they own or that have been shared with them.
- Server owners can grant an existing non-admin account access to one server. No invitation email is sent; the recipient must already have an active LPGP account.
- Every membership receives `server.read` plus only the selected grants: console, start/stop/restart, file read/write, backup read/create/restore, and Minecraft management/version upgrades.
- Server-specific API routes check the required permission on every request. Panel administrator accounts retain administrative access. Team members cannot manage membership, access VPS node administration, create servers, or delete the owner's server.
- Owners can list and revoke team memberships. Grants are stored in a dedicated `server_subusers` table with a unique server/user pair and foreign-key cleanup.
- Apply the new database migration with `cd backend && alembic upgrade head` before starting the updated API.
- The phase does not include email invitations, customer billing, quotas, or customer self-service provisioning.

## Phase 10 — billing, observability and production controls

### Stripe billing
- Customers can start a recurring Stripe Checkout session for the administrator-configured Stripe Price ID, open the Stripe Billing Portal, and view invoice history.
- The API never receives or stores card numbers. Configure `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, and `FRONTEND_URL` in the backend environment.
- Register `POST https://YOUR_API_HOST/api/v1/billing/webhook` in Stripe. Subscribe to `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, and `invoice.payment_failed`.
- Webhook signatures use Stripe's timestamped HMAC scheme with a five-minute tolerance. Processed event IDs are stored for retry idempotency. Subscription and invoice records are scoped to the authenticated account.
- Billing is an integration foundation: no server quotas, automatic suspension for failed payments, tax calculation, coupons, or metered usage enforcement are enabled yet. Configure products/prices and webhook delivery in Stripe before enabling customer payments.

### Operations and security
- `GET /api/v1/health/live` is a liveness probe; `GET /api/v1/health/ready` checks database connectivity.
- Authenticated administrators can view live server/node/task/account counters at `GET /api/v1/admin/metrics`.
- API requests receive request IDs and security headers. Login requests have a stricter per-IP rate limit; all other routes have a configurable per-IP limit through `RATE_LIMIT_PER_MINUTE`.
- The limiter is in-process. It is useful for a single API instance, but is not a distributed limit across multiple workers/replicas. Use a shared Redis-backed gateway limiter for horizontally scaled production deployments.
- In `ENVIRONMENT=production`, interactive API documentation is disabled, localhost CORS origins are rejected, and `ALLOWED_HOSTS` must explicitly list the public panel/API hostnames.
- Put the API behind HTTPS, configure a reverse proxy with a strict body-size limit, restrict database/network access, keep Stripe and node secrets out of source control, and back up PostgreSQL plus node-local game backups independently.
- Run the database migration before deploying the API: `cd backend && alembic upgrade head`.

### Phase 10 deployment settings
Set `ENVIRONMENT=production`, a unique `SECRET_KEY`, exact `CORS_ORIGINS`, and comma-separated `ALLOWED_HOSTS`. Set `FRONTEND_URL` to the HTTPS panel origin. Billing remains unavailable until all three Stripe settings are configured.


## Additional server management features

- **Scheduled backups:** administrators and server owners can schedule hourly, daily, or weekly node-local snapshots with a configurable retention count. The node agent dispatches due jobs through the authenticated task queue and prunes older scheduled snapshots. Backups remain on the VPS and should be copied to independent storage for disaster recovery.
- **Paper, Fabric, and Forge runtimes:** new servers can select one of these itzg Minecraft server types. Existing servers are migrated as Paper by default.
- **Plugin and mod management:** Paper plugin JARs and Fabric/Forge mod JARs can be listed, installed, and removed. Installs accept direct HTTPS JAR URLs only from an explicit Modrinth, Hangar, or CurseForge CDN allowlist, enforce download/archive limits, verify expected JAR metadata, and stop/restart the server around file changes. This is not a malware scanner; only install files from sources you trust.

SFTP service exposure, database container provisioning, multi-allocation lifecycle management, API-key management, remote backup storage, and production multi-tenant hardening remain separate work items. Do not expose the panel as a public multi-customer service until those deployment controls and a real VPS acceptance test are complete.


- **Multi-allocation support:** each server can have up to 10 additional TCP/UDP host-to-container port mappings. Updating mappings queues a node task which safely recreates the managed container while retaining its persistent data volume. Extra container ports must be used by a plugin or service configured to listen on those ports; adding a mapping alone does not make Minecraft listen on it.


- **Per-server SFTP:** an isolated SFTPGo container is provisioned for each server, mounting only that server's managed data volume. The panel creates a one-time password, stores only its hash in the SFTP access record, and exposes a dedicated TCP port. Operators must allow the assigned SFTP port range (31000–31999) in their VPS firewall. The SFTPGo admin API is not published on the host.
- **Personal API keys:** non-admin accounts can create, list, and revoke expiring read-only API keys. Tokens are hashed in the panel database, shown once, and cannot perform server control or administrative actions. Administrator API keys are intentionally disabled.


- **Managed databases:** up to three MariaDB or PostgreSQL containers per server, each with a persistent Docker volume, unique host port, and a dedicated per-server Docker bridge network shared with the Minecraft container. The panel returns the generated database password once and stores only its hash in the database-service record. External DB access is exposed on the assigned node port; firewall allowlisting is strongly recommended. The internal database hostname is available to processes in the server's private Docker network.
