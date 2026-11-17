#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash install.sh"; exit 1; fi
read -r -p "Lighting Panel API base URL (https://panel.example.com): " PANEL_URL
read -r -s -p "One-time node token: " NODE_TOKEN
echo
if [[ "$PANEL_URL" != https://* && "$PANEL_URL" != http://127.0.0.1* ]]; then echo "The panel URL must use HTTPS."; exit 1; fi
if [[ ${#NODE_TOKEN} -lt 32 ]]; then echo "Invalid node token."; exit 1; fi
apt-get update
apt-get install -y python3 python3-venv docker.io
systemctl enable --now docker
install -d -m 0750 /opt/lighting-node-agent /etc/lighting-agent
cp agent.py requirements.txt /opt/lighting-node-agent/
python3 -m venv /opt/lighting-node-agent/.venv
/opt/lighting-node-agent/.venv/bin/pip install --upgrade pip
/opt/lighting-node-agent/.venv/bin/pip install -r /opt/lighting-node-agent/requirements.txt
cat > /etc/lighting-agent/agent.env <<EOF
PANEL_URL=$PANEL_URL
NODE_TOKEN=$NODE_TOKEN
EOF
chmod 0600 /etc/lighting-agent/agent.env
cat > /etc/systemd/system/lighting-node-agent.service <<'EOF'
[Unit]
Description=Lighting Panel VPS Node Telemetry Agent
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=root
Environment=LIGHTING_AGENT_ENV=/etc/lighting-agent/agent.env
ExecStart=/opt/lighting-node-agent/.venv/bin/python /opt/lighting-node-agent/agent.py
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/etc/lighting-agent
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now lighting-node-agent
echo "Lighting node telemetry agent installed."
echo "Check: systemctl status lighting-node-agent"
