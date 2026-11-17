# Lighting Panel

A modern game-server control-panel frontend prototype inspired by the workflows of Pterodactyl. This repository is being built as an independent project; it does not include or copy Pterodactyl source code or assets.

## Current status

The first commit establishes a responsive React/Vite dashboard with a server list, local demo start/stop controls, local create-server interaction, resource overview, activity presentation, and navigation placeholders. Demo metrics and server records are local sample data; no real server process is controlled yet.

## Requirements

- Node.js 20.19+ or 22.12+
- npm

## Run locally

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## Planned production architecture

1. Authentication, sessions, roles and permission enforcement.
2. API service (Python FastAPI) with PostgreSQL and Redis-backed jobs.
3. Node agent installed on each VPS; authenticated outbound registration to the panel, with TLS and short-lived credentials.
4. Isolated server runtime using Docker/containerd; never expose a privileged Docker socket to the browser.
5. Server lifecycle, console streaming, file manager, SFTP, schedules, backups, databases, allocations and resource telemetry.
6. Admin controls, audit logs, billing integration and security hardening.

The UI must not report a server as deployed or running until the backend and node agent confirm the real state. Keep secrets out of the frontend and never execute user-supplied shell commands through an unauthenticated endpoint.
