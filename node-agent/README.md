# Lighting Node Agent — Phase 4

The first node-agent release reports host CPU, memory and disk telemetry to the panel. It does not yet create containers or run user workloads; container lifecycle will use an isolated runtime adapter in a later phase.

## Enroll and install

1. Sign in as an administrator.
2. Create a node using POST /api/v1/admin/nodes with JSON: {"name":"vps-01","fqdn":"node01.example.com"}.
3. Save the returned one-time token. It is shown only at creation.
4. Copy agent.py, requirements.txt and install.sh to the VPS.
5. Run sudo bash install.sh and provide the panel HTTPS URL and token.

Check the service with systemctl status lighting-node-agent and journalctl -u lighting-node-agent -f.

## Security

- Use HTTPS with a valid certificate for remote panels. Certificate verification is enabled.
- The node credential is stored hashed in the panel database and plaintext only in root-readable mode-0600 configuration on the VPS.
- Never paste node tokens into chat, logs, Git, or browser frontend code.
- Disable a compromised node in the panel. Token rotation is planned.
- The current service runs as root to read host-wide metrics. It has no Docker socket access and does not execute user commands.
