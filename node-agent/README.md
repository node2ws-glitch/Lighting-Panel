# Lighting Node Agent

The VPS node agent reports host telemetry and executes a constrained set of Lighting Panel server lifecycle tasks through Docker Engine. It does not accept arbitrary shell commands or arbitrary image names from the panel.

## Enroll and install

1. Sign in to Lighting Panel as an administrator.
2. Create a node in the Nodes page and copy the one-time token.
3. Copy `agent.py`, `requirements.txt`, and `install.sh` to the target Ubuntu/Debian VPS.
4. Run `sudo bash install.sh` and enter the public panel HTTPS URL and node token.
5. The installer installs Docker Engine, installs the Python agent in an isolated virtual environment, stores the token in a root-only configuration file, and enables a systemd service.

Check the service:

```bash
systemctl status lighting-node-agent
journalctl -u lighting-node-agent -f
docker ps --filter label=net.lightingpanel.managed=true
```

## Server runtime

The current runtime adapter supports Minecraft Java using the `itzg/minecraft-server:java21` image with Paper. Each server gets:
- A dedicated Docker container and persistent named volume.
- A dedicated TCP allocation from the panel allocation range.
- Memory and CPU limits configured at container creation.
- Container labels used to verify ownership before lifecycle actions.
- `start`, `stop`, `restart`, and `delete` task operations.

The node agent only executes the fixed `provision`, `start`, `stop`, `restart`, and `delete` task types. The panel never supplies a raw Docker command, image name, host path, or shell command. Deleting a server also deletes its persistent world volume and is irreversible.

## Network

Open the assigned TCP allocation range (currently 25565–25999) in the VPS firewall/security group to permit Minecraft clients to connect. Keep the Docker daemon socket private; never expose it over TCP. Use a trusted HTTPS certificate for the panel API.

## Security and operations

- Node credentials are stored as SHA-256 hashes in the panel database and plaintext only in root-readable mode-0600 config on the VPS.
- Disable a compromised node from the panel. Credential rotation is not implemented yet.
- Docker access is highly privileged. Run this agent only on dedicated hosting nodes you administer.
- The current agent runs as root to read host-wide metrics and access the Docker socket.
- Docker container resource limits are enforced by the daemon. Host firewall, disk quotas, image update policy, console streaming, and container health reconciliation are still required before multi-tenant production use.
- Task claims have a two-minute lease so interrupted work can be retried after the lease expires.

## Console and file tasks

The agent also supports `console`, `console_logs`, and `file_list`, `file_read`, `file_write`, `file_mkdir`, `file_delete`, and `file_rename` tasks. Minecraft commands are written to the container's attached stdin; no shell is involved. File operations are restricted to the server's `/data` volume after path resolution. Symlinks are omitted, only regular files can be deleted, and editor reads/writes are capped at 512 KiB. The panel's browser file manager supports small uploads and downloads.

Console output is polled through the task API and is not a persistent WebSocket stream. SFTP is not enabled yet. Update the agent files and restart `lighting-node-agent` on every node before using these features.

