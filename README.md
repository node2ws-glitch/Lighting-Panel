# Lighting Panel

Lighting Panel is an independent game-server hosting control plane with a dark, electric visual identity. It is inspired by common hosting-panel workflows; it does not copy Pterodactyl source code or assets.

## Implemented foundations

- Responsive React/Vite panel with animated dark UI and protected sign-in.
- FastAPI backend with PostgreSQL, SQLAlchemy and Alembic migrations.
- Argon2 password hashing, short-lived JWT authentication, administrator roles and audit events.
- VPS node enrollment, one-time node credentials and authenticated CPU/RAM/disk telemetry.
- Docker-backed Minecraft Java provisioning through the node agent.
- Persistent per-server Docker volumes, dedicated TCP allocations, CPU/RAM limits and queued start/stop/restart/delete operations.
- Node task leases for retrying interrupted work.
- GitHub Actions frontend build, backend tests and migration checks.

## Current runtime boundaries

The server list, deployment form and lifecycle controls use the real API and node task queue. A connected Linux node with Docker Engine and the current agent can provision Minecraft Java (Paper) containers. Provisioning is asynchronous: the node pulls the Minecraft image and reports completion to the panel.

This is an early single-node runtime, not yet a production-hardened Pterodactyl replacement. Console streaming, file manager/SFTP, backups, schedules, database provisioning, multi-allocation management, per-customer permissions, billing, disk quotas, image update policy, firewall automation, token rotation and comprehensive container health reconciliation remain future phases. The dashboard overview still contains sample analytics and needs to be connected to live aggregate metrics. Do not expose this deployment to untrusted tenants until the remaining isolation and operational controls are implemented.

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
6. Live console, file manager and SFTP.
7. Minecraft server configuration, versions and server properties.
8. Backups, schedules, databases and allocations.
9. Subusers, granular permissions and customer management.
10. Billing, observability, rate limits, security audit and production deployment.

The project should only mark a phase complete after its tests and end-to-end acceptance checks pass.
