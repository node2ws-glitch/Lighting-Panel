# Lighting Panel API — Phase 2

FastAPI backend foundation with PostgreSQL support, SQLAlchemy models, Alembic migrations, Argon2 password hashing, short-lived JWT access tokens, database-backed role checks, administrator user management, and audit events.

## Local development

Python 3.11+ is recommended.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set a unique SECRET_KEY (at least 32 random bytes) and DATABASE_URL. For quick local testing use `sqlite:///./lighting_panel.db`; PostgreSQL is recommended for deployment.

```bash
alembic upgrade head
python scripts/create_admin.py --email admin@example.com --username admin
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

## Routes

- `POST /api/v1/auth/login` — email/password sign-in; returns a short-lived bearer token.
- `GET /api/v1/auth/me` — current account.
- `POST /api/v1/auth/logout` — audit event; client discards its short-lived token.
- `GET /api/v1/admin/users` — administrator-only user list.
- `POST /api/v1/admin/users` — administrator-only user creation (12+ character password).
- `PATCH /api/v1/admin/users/{id}/status?is_active=false` — administrator-only account activation control.
- `GET /api/v1/admin/audit` — administrator-only audit log.
- `GET /api/v1/health` — health endpoint.

## Production notes

Keep `.env` private; use a unique high-entropy SECRET_KEY, HTTPS, exact CORS origins, rate limiting at the reverse proxy, and private database networking. Run Alembic migrations as a deployment step. Access tokens expire after 20 minutes by default. Logout currently records an audit event and relies on the client discarding the short-lived token; implement token revocation/refresh tokens before long-lived sessions. Public self-registration is disabled. Never commit production secrets.


## VPS nodes and server runtime

- `POST /api/v1/admin/nodes` — enroll a node and receive a one-time token.
- `GET /api/v1/admin/nodes` — list node telemetry.
- `PATCH /api/v1/admin/nodes/{id}/status?is_enabled=false` — disable a node credential.
- `POST /api/v1/nodes/heartbeat` — authenticated host telemetry.
- `GET /api/v1/admin/servers` — list server instances.
- `POST /api/v1/admin/servers` — queue a Minecraft Java deployment on an online node.
- `POST /api/v1/admin/servers/{id}/action` — queue start, stop, restart or delete.
- `GET /api/v1/nodes/tasks` — node agent claims pending tasks.
- `POST /api/v1/nodes/tasks/{id}/result` — node agent reports completion or failure.

Server provisioning uses a fixed Paper Minecraft image, persistent Docker volume, allocated host TCP port, and configured memory/CPU limits. The node agent only executes the supported task allowlist and checks container ownership labels before lifecycle operations. See ../node-agent/README.md for installation and operational requirements.

The first runtime release is not a full multi-tenant security boundary. Add console/file access permissions, disk quotas, network policy, task idempotency/monitoring, and security review before accepting untrusted customers.
