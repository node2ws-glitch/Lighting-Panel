import os
import sys
import time
import socket
import logging
from pathlib import Path
import psutil
import requests

CONFIG = Path(os.environ.get('LIGHTING_AGENT_ENV', '/etc/lighting-agent/agent.env'))
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'), format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('lighting-agent')

def load_config():
    if CONFIG.exists():
        for raw in CONFIG.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())
    panel = os.getenv('PANEL_URL', '').rstrip('/')
    token = os.getenv('NODE_TOKEN', '')
    if not panel.startswith('https://') and not panel.startswith('http://127.0.0.1'):
        raise RuntimeError('PANEL_URL must use HTTPS (HTTP is allowed only for localhost testing)')
    if len(token) < 32:
        raise RuntimeError('NODE_TOKEN is missing or too short')
    return panel, token

def sample():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return {'cpu_percent': psutil.cpu_percent(interval=1), 'memory_total': memory.total, 'memory_used': memory.used, 'disk_total': disk.total, 'disk_used': disk.used}

def main():
    panel, token = load_config()
    session = requests.Session()
    session.headers.update({'X-Node-Token': token, 'Content-Type': 'application/json', 'User-Agent': 'LightingNodeAgent/0.1'})
    log.info('Node telemetry agent started for %s', socket.gethostname())
    while True:
        try:
            response = session.post(panel + '/api/v1/nodes/heartbeat', json=sample(), timeout=(5, 10))
            if response.status_code == 401:
                raise RuntimeError('Node credential rejected; disable service and re-enroll this node')
            response.raise_for_status()
            log.debug('Heartbeat accepted')
        except requests.RequestException as exc:
            log.warning('Panel heartbeat failed: %s', exc)
        except RuntimeError:
            log.exception('Fatal node authentication error')
            return 2
        time.sleep(15)
    return 0

if __name__ == '__main__':
    sys.exit(main())
