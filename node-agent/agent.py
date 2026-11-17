import base64
import json
import logging
import os
import socket
import sys
import time
from pathlib import Path

import docker
import psutil
import requests

CONFIG = Path(os.environ.get('LIGHTING_AGENT_ENV', '/etc/lighting-agent/agent.env'))
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'), format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('lighting-agent')
IMAGE = 'itzg/minecraft-server:java21'
LABEL_OWNER = 'net.lightingpanel.managed'

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

def container_name(server_id):
    return f'lighting-server-{int(server_id)}'


def safe_server_path(relative):
    root = Path('/data').resolve()
    candidate = (root / str(relative)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError('Path must remain inside the server data directory')
    if candidate == root and str(relative) not in ('.', './', ''):
        raise ValueError('Invalid server file path')
    return candidate

def run_file_operation(container, payload):
    operation = payload.get('operation')
    relative = payload.get('path', '.')
    target = safe_server_path(relative)
    if operation == 'list':
        if not target.exists() or not target.is_dir():
            raise ValueError('Directory does not exist')
        entries = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:200]:
            if item.is_symlink():
                continue
            entries.append({'name':item.name,'path':item.relative_to(Path('/data')).as_posix(),'directory':item.is_dir(),
                'size':item.stat().st_size if item.is_file() else 0,'modified':int(item.stat().st_mtime)})
        return {'entries':entries,'path':target.relative_to(Path('/data')).as_posix() or '.'}
    if operation == 'read':
        if not target.is_file():
            raise ValueError('File does not exist')
        if target.stat().st_size > 512 * 1024:
            raise ValueError('File exceeds the 512 KB editor limit; use SFTP for large files')
        return {'path':target.relative_to(Path('/data')).as_posix(),'content_base64':base64.b64encode(target.read_bytes()).decode('ascii')}
    if operation == 'write':
        if target.exists() and not target.is_file():
            raise ValueError('Target is not a regular file')
        encoded = payload.get('content_base64')
        if not isinstance(encoded, str):
            raise ValueError('File content is missing')
        try:
            content = base64.b64decode(encoded, validate=True)
        except Exception:
            raise ValueError('File content encoding is invalid')
        if len(content) > 512 * 1024:
            raise ValueError('File exceeds the 512 KB editor limit')
        if not target.parent.exists() or not target.parent.is_dir():
            raise ValueError('Parent directory does not exist')
        target.write_bytes(content)
        return {'path':target.relative_to(Path('/data')).as_posix(),'bytes_written':len(content)}
    if operation == 'mkdir':
        if target.exists():
            raise ValueError('Path already exists')
        target.mkdir()
        return {'path':target.relative_to(Path('/data')).as_posix()}
    if operation == 'delete':
        if not target.is_file():
            raise ValueError('Only individual files can be deleted from the panel')
        target.unlink()
        return {'deleted':relative}
    if operation == 'rename':
        destination = safe_server_path(payload.get('destination', ''))
        if not target.exists() or destination.exists() or not destination.parent.is_dir():
            raise ValueError('Source or destination is invalid')
        target.rename(destination)
        return {'path':destination.relative_to(Path('/data')).as_posix()}
    raise ValueError('Unsupported file operation')

def run_console_operation(container, action, payload):
    if container.status != 'running':
        raise RuntimeError('Minecraft container is not running')
    if action == 'console':
        command = str(payload.get('command', '')).strip()
        if not command or len(command) > 512 or any(ord(ch) < 32 for ch in command):
            raise ValueError('Invalid console command')
        stream = container.attach_socket(params={'stdin':1,'stream':1,'logs':0})
        try:
            sock = getattr(stream, '_sock', stream)
            sock.sendall((command + '\\n').encode('utf-8'))
        finally:
            stream.close()
        return {'accepted':True,'command':command}
    if action == 'console_logs':
        raw = container.logs(stdout=True, stderr=True, tail=120, since=max(0,int(time.time())-45), timestamps=True)
        return {'output':raw.decode('utf-8', errors='replace')[-48000:]}
    raise ValueError('Unsupported console operation')

def run_task(client, task):
    action = task.get('action')
    payload = task.get('payload') or {}
    server_id = int(payload.get('server_id', task.get('server_id') or 0))
    if server_id <= 0:
        raise ValueError('Task has no valid server id')
    name = container_name(server_id)
    if action == 'provision':
        version = str(payload.get('version', 'LATEST'))
        if version != 'LATEST' and not __import__('re').fullmatch(r'\d+\.\d+(\.\d+)?', version):
            raise ValueError('Unsupported Minecraft version format')
        memory_mb = int(payload.get('memory_mb', 0))
        cpu_limit = float(payload.get('cpu_limit', 0))
        port = int(payload.get('port', 0))
        if not 512 <= memory_mb <= 16384 or not 0.5 <= cpu_limit <= 16 or not 25565 <= port <= 25999:
            raise ValueError('Server resource or port values are outside allowed limits')
        try:
            existing = client.containers.get(name)
            if existing.labels.get(LABEL_OWNER) != 'true' or existing.labels.get('net.lightingpanel.server-id') != str(server_id):
                raise RuntimeError('Container name collision; refusing to modify an unmanaged container')
            if existing.status != 'running':
                existing.start()
            return {'docker_id': existing.id}
        except docker.errors.NotFound:
            pass
        volume = f'lighting-server-data-{server_id}'
        client.volumes.create(name=volume, labels={LABEL_OWNER:'true','net.lightingpanel.server-id':str(server_id)})
        container = client.containers.run(
            IMAGE,
            name=name,
            detach=True,
            environment={'EULA':'TRUE','TYPE':'PAPER','VERSION':version,'MEMORY':f'{int(memory_mb * 0.8)}M','TZ':'UTC'},
            ports={'25565/tcp':('0.0.0.0',port)},
            volumes={volume:{'bind':'/data','mode':'rw'}},
            mem_limit=f'{memory_mb}m',
            nano_cpus=int(cpu_limit * 1_000_000_000),
            pids_limit=512,
            init=True,
            tty=True,
            stdin_open=True,
            labels={LABEL_OWNER:'true','net.lightingpanel.server-id':str(server_id)},
            restart_policy={'Name':'unless-stopped'},
            cap_drop=['NET_RAW','SYS_CHROOT','MKNOD'],
            security_opt=['no-new-privileges:true'],
        )
        return {'docker_id':container.id}
    try:
        container = client.containers.get(name)
    except docker.errors.NotFound:
        if action == 'delete':
            try:
                volume = client.volumes.get(f'lighting-server-data-{server_id}')
                if volume.attrs.get('Labels', {}).get(LABEL_OWNER) == 'true':
                    volume.remove(force=False)
            except docker.errors.NotFound:
                pass
            return {'docker_id':None}
        raise RuntimeError('Managed server container does not exist')
    if container.labels.get(LABEL_OWNER) != 'true' or container.labels.get('net.lightingpanel.server-id') != str(server_id):
        raise RuntimeError('Refusing to operate on a container not owned by Lighting Panel')
    if action in ('console','console_logs'):
        return {'data':run_console_operation(container, action, payload)}
    if action.startswith('file_'):
        return {'data':run_file_operation(container, payload)}
    if action == 'start':
        if container.status != 'running':
            container.start()
    elif action == 'stop':
        if container.status == 'running':
            container.stop(timeout=30)
    elif action == 'restart':
        container.restart(timeout=30)
    elif action == 'delete':
        container.remove(force=True)
        try:
            volume = client.volumes.get(f'lighting-server-data-{server_id}')
            if volume.attrs.get('Labels', {}).get(LABEL_OWNER) == 'true':
                volume.remove(force=False)
        except docker.errors.NotFound:
            pass
        return {'docker_id':None}
    else:
        raise ValueError('Unsupported node task action')
    return {'docker_id':container.id}

def report_result(session, endpoint, task_id, result):
    response = session.post(f'{endpoint}/api/v1/nodes/tasks/{task_id}/result', json=result, timeout=(5,15))
    response.raise_for_status()

def main():
    panel, token = load_config()
    endpoint = panel
    session = requests.Session()
    session.headers.update({'X-Node-Token':token,'Content-Type':'application/json','User-Agent':'LightingNodeAgent/0.2'})
    client = docker.from_env(timeout=30)
    client.ping()
    log.info('Lighting node agent connected to Docker on %s', socket.gethostname())
    while True:
        try:
            heartbeat = session.post(endpoint+'/api/v1/nodes/heartbeat', json=sample(), timeout=(5,10))
            if heartbeat.status_code == 401:
                raise RuntimeError('Node credential rejected; disable service and re-enroll this node')
            heartbeat.raise_for_status()
            tasks_response = session.get(endpoint+'/api/v1/nodes/tasks', timeout=(5,10))
            tasks_response.raise_for_status()
            for task in tasks_response.json():
                try:
                    result = run_task(client, task)
                    report_result(session, endpoint, task['id'], result)
                    log.info('Completed node task %s (%s)', task['id'], task['action'])
                except Exception as exc:
                    log.exception('Node task %s failed', task.get('id'))
                    try:
                        report_result(session, endpoint, task['id'], {'error':str(exc)[:950]})
                    except requests.RequestException:
                        log.exception('Could not report task failure')
        except requests.RequestException as exc:
            log.warning('Panel connection failed: %s', exc)
        except RuntimeError:
            log.exception('Fatal node authentication or Docker error')
            return 2
        time.sleep(5)
    return 0

if __name__ == '__main__':
    sys.exit(main())
