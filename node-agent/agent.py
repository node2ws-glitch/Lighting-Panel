import base64
import json
import logging
import os
import socket
import sys
import time
import tarfile
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import docker
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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


BACKUP_ROOT = Path('/var/lib/lighting-panel/backups')
MAX_BACKUP_BYTES = 20 * 1024 * 1024 * 1024

def server_volume(client, server_id):
    volume = client.volumes.get(f'lighting-server-data-{int(server_id)}')
    labels = volume.attrs.get('Labels', {}) or {}
    if labels.get(LABEL_OWNER) != 'true' or labels.get('net.lightingpanel.server-id') != str(server_id):
        raise RuntimeError('Server volume ownership validation failed')
    mountpoint = Path(volume.attrs['Mountpoint']).resolve()
    if not mountpoint.is_dir():
        raise RuntimeError('Server volume mountpoint is unavailable')
    return volume, mountpoint

def backup_directory(server_id):
    directory = BACKUP_ROOT / str(int(server_id))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    return directory

def create_server_backup(client, server_id, mountpoint, label='manual'):
    total = sum(p.stat().st_size for p in mountpoint.rglob('*') if p.is_file() and not p.is_symlink())
    if total > MAX_BACKUP_BYTES:
        raise ValueError('Server data exceeds the 20 GiB per-backup safety limit')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_id = f'{stamp}-{uuid.uuid4().hex[:10]}'
    directory = backup_directory(server_id)
    target = directory / f'{backup_id}.tar.gz'
    temporary = directory / f'.{backup_id}.tmp'
    try:
        with tarfile.open(temporary, 'w:gz', compresslevel=3) as archive:
            for root, directories, filenames in os.walk(mountpoint, followlinks=False):
                root_path = Path(root)
                directories[:] = sorted(name for name in directories if not (root_path / name).is_symlink())
                archive.add(root_path, arcname=root_path.relative_to(mountpoint).as_posix() or '.', recursive=False)
                for filename in sorted(filenames):
                    item = root_path / filename
                    if not item.is_symlink() and item.is_file():
                        archive.add(item, arcname=item.relative_to(mountpoint).as_posix(), recursive=False)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {'id':backup_id,'filename':target.name,'size_bytes':target.stat().st_size,'created_at':stamp,'label':label}

def list_server_backups(server_id):
    directory = backup_directory(server_id)
    output = []
    for item in sorted(directory.glob('*.tar.gz'), key=lambda p:p.name, reverse=True)[:100]:
        backup_id = item.name[:-7]
        if not __import__('re').fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{10}', backup_id):
            continue
        output.append({'id':backup_id,'filename':item.name,'size_bytes':item.stat().st_size,'created_at':backup_id[:16]})
    return output

def restore_server_backup(client, server_id, container, mountpoint, backup_id):
    if not __import__('re').fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{10}', str(backup_id)):
        raise ValueError('Invalid backup identifier')
    directory = backup_directory(server_id).resolve()
    archive_path = (directory / (str(backup_id)+'.tar.gz')).resolve()
    if archive_path.parent != directory or not archive_path.is_file():
        raise ValueError('Backup does not exist on this node')
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            name = Path(member.name)
            if name.is_absolute() or '..' in name.parts or member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ValueError('Backup contains an unsafe archive entry')
    was_running = container.status == 'running'
    if was_running:
        container.stop(timeout=30)
    try:
        create_server_backup(client, server_id, mountpoint, label='pre-restore')
        for child in mountpoint.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        with tarfile.open(archive_path, 'r:gz') as archive:
            archive.extractall(mountpoint, members=members)
    except Exception:
        if was_running:
            container.start()
        raise
    if was_running:
        container.start()
    return {'restored_backup':backup_id,'previous_state':'running' if was_running else 'stopped'}


def ensure_server_network(client, server_id):
    name = f'lighting-server-net-{int(server_id)}'
    try:
        network = client.networks.get(name)
    except docker.errors.NotFound:
        network = client.networks.create(name, driver='bridge',
            labels={LABEL_OWNER:'true','net.lightingpanel.server-id':str(server_id)})
    labels = network.attrs.get('Labels', {}) or {}
    if labels.get(LABEL_OWNER) != 'true' or labels.get('net.lightingpanel.server-id') != str(server_id):
        raise RuntimeError('Server network ownership validation failed')
    return network

def create_minecraft_container(client, server_id, version, memory_mb, cpu_limit, port, server_type='paper', extra_allocations=None):
    ports = {'25565/tcp': ('0.0.0.0', int(port))}
    for item in extra_allocations or []:
        container_port = int(item.get('container_port', 0)); host_port = int(item.get('port', 0)); protocol = str(item.get('protocol', 'tcp'))
        if not 1024 <= container_port <= 65535 or not 1024 <= host_port <= 65535 or protocol not in ('tcp', 'udp'):
            raise ValueError('Additional allocation is invalid')
        key = f'{container_port}/{protocol}'
        if key in ports:
            raise ValueError('Duplicate container port and protocol')
        ports[key] = ('0.0.0.0', host_port)
    network = ensure_server_network(client, server_id)
    container = client.containers.run(
        IMAGE, name=container_name(server_id), detach=True,
        environment={'EULA':'TRUE','TYPE':str(server_type).upper(),'VERSION':version,'MEMORY':f'{int(memory_mb * 0.8)}M','TZ':'UTC'},
        ports=ports, network=network.name,
        volumes={f'lighting-server-data-{server_id}':{'bind':'/data','mode':'rw'}},
        mem_limit=f'{int(memory_mb)}m', nano_cpus=int(float(cpu_limit)*1_000_000_000),
        pids_limit=512, init=True, tty=True, stdin_open=True,
        labels={LABEL_OWNER:'true','net.lightingpanel.server-id':str(server_id)},
        restart_policy={'Name':'unless-stopped'}, cap_drop=['NET_RAW','SYS_CHROOT','MKNOD'],
        security_opt=['no-new-privileges:true'])
    return container

def upgrade_minecraft_server(client, server_id, container, payload):
    version = str(payload.get('version',''))
    if not __import__('re').fullmatch(r'\d+\.\d+(\.\d+)?', version):
        raise ValueError('Choose a valid Minecraft release version')
    memory_mb = int(payload.get('memory_mb',0)); cpu_limit = float(payload.get('cpu_limit',0)); port = int(payload.get('port',0)); server_type = str(payload.get('server_type', 'paper')).lower()
    if server_type not in ('paper','fabric','forge'):
        raise ValueError('Unsupported Minecraft server type')
    if not 512 <= memory_mb <= 16384 or not 0.5 <= cpu_limit <= 16 or not 25565 <= port <= 25999:
        raise ValueError('Server resource settings are invalid')
    _, mountpoint = server_volume(client, server_id)
    old_version = str(payload.get('previous_version','LATEST'))
    was_running = container.status == 'running'
    if was_running:
        container.stop(timeout=30)
    try:
        create_server_backup(client, server_id, mountpoint, label='pre-upgrade')
        container.remove(v=False)
        client.images.pull(IMAGE)
        replacement = create_minecraft_container(client, server_id, version, memory_mb, cpu_limit, port, server_type)
        return {'version':version,'docker_id':replacement.id,'backup_created':True}
    except Exception:
        try:
            create_minecraft_container(client, server_id, old_version, memory_mb, cpu_limit, port, server_type)
        except Exception:
            log.exception('Could not recreate previous Minecraft version after failed upgrade')
        raise

def run_backup_task(client, action, payload, server_id, container):
    _, mountpoint = server_volume(client, server_id)
    if action == 'backup_list':
        return {'backups':list_server_backups(server_id)}
    if action == 'backup_create':
        was_running = container.status == 'running'
        if was_running:
            container.stop(timeout=30)
        try:
            label = str(payload.get('label', 'manual'))[:32]
            item = create_server_backup(client, server_id, mountpoint, label=label)
            retention = int(payload.get('retention', 100))
            if not 1 <= retention <= 100:
                raise ValueError('Backup retention must be between 1 and 100')
            if label == 'scheduled':
                backups = list_server_backups(server_id)
                for obsolete in backups[retention:]:
                    candidate = (backup_directory(server_id) / (obsolete['id'] + '.tar.gz')).resolve()
                    if candidate.parent == backup_directory(server_id).resolve() and candidate.is_file():
                        candidate.unlink()
        finally:
            if was_running:
                container.start()
        return {'backup':item,'backups':list_server_backups(server_id)}
    if action == 'backup_restore':
        return restore_server_backup(client, server_id, container, mountpoint, payload.get('backup_id',''))
    raise ValueError('Unsupported backup operation')


def run_mod_manager(client, server_id, container, payload):
    kind = str(payload.get('kind', ''))
    action = str(payload.get('action', ''))
    if kind not in ('plugin', 'mod') or action not in ('list', 'install', 'remove'):
        raise ValueError('Unsupported mod manager operation')
    _, mountpoint = server_volume(client, server_id)
    folder = 'plugins' if kind == 'plugin' else 'mods'
    target_dir = (mountpoint / folder).resolve()
    if target_dir.parent != mountpoint.resolve():
        raise ValueError('Invalid managed directory')
    target_dir.mkdir(mode=0o755, exist_ok=True)
    if action == 'list':
        return {'kind':kind,'files':[{'filename':p.name,'size_bytes':p.stat().st_size} for p in sorted(target_dir.glob('*.jar')) if p.is_file() and not p.is_symlink()][:200]}
    filename = str(payload.get('filename') or '')
    if not __import__('re').fullmatch(r'[A-Za-z0-9_. -]{1,120}\.jar', filename):
        raise ValueError('Invalid JAR filename')
    target = (target_dir / filename).resolve()
    if target.parent != target_dir:
        raise ValueError('Invalid JAR path')
    was_running = container.status == 'running'
    if was_running:
        container.stop(timeout=30)
    try:
        if action == 'remove':
            if not target.is_file() or target.is_symlink():
                raise ValueError('JAR file does not exist')
            target.unlink()
            return {'kind':kind,'removed':filename,'files':[{'filename':p.name,'size_bytes':p.stat().st_size} for p in target_dir.glob('*.jar') if p.is_file() and not p.is_symlink()][:200]}
        url = str(payload.get('url') or '')
        allowed_hosts = {'cdn.modrinth.com','hangarcdn.papermc.io','mediafilez.forgecdn.net','edge.forgecdn.net'}
        if not url.startswith('https://'):
            raise ValueError('Only HTTPS downloads are accepted')
        import urllib.parse
        current = url
        response = None
        for _ in range(4):
            parsed = urllib.parse.urlparse(current)
            if parsed.scheme != 'https' or parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
                raise ValueError('Download host is not on the trusted Modrinth, Hangar, or CurseForge CDN allowlist')
            response = requests.get(current, stream=True, timeout=(10,30), allow_redirects=False)
            if response.is_redirect:
                location = response.headers.get('Location')
                response.close()
                if not location:
                    raise ValueError('Download redirect did not include a location')
                current = urllib.parse.urljoin(current, location)
                continue
            response.raise_for_status()
            break
        else:
            raise ValueError('Too many download redirects')
        length = int(response.headers.get('Content-Length') or 0)
        if length > 100 * 1024 * 1024:
            response.close()
            raise ValueError('JAR downloads are limited to 100 MB')
        temporary = target_dir / ('.' + uuid.uuid4().hex + '.part')
        total = 0
        try:
            with temporary.open('wb') as output:
                for chunk in response.iter_content(1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > 100 * 1024 * 1024:
                        raise ValueError('JAR download exceeded the 100 MB limit')
                    output.write(chunk)
            if not zipfile.is_zipfile(temporary):
                raise ValueError('Downloaded file is not a valid Java archive')
            with zipfile.ZipFile(temporary) as jar:
                names = set(jar.namelist())
                markers = {'plugin.yml','paper-plugin.yml'} if kind == 'plugin' else {'fabric.mod.json','quilt.mod.json','META-INF/mods.toml'}
                if not any(name in names for name in markers):
                    raise ValueError('JAR does not contain a recognized '+kind+' metadata file')
                if len(names) > 50000 or sum(item.file_size for item in jar.infolist()) > 300 * 1024 * 1024:
                    raise ValueError('JAR archive exceeds safety limits')
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            response.close()
        return {'kind':kind,'installed':filename,'bytes':total,'files':[{'filename':p.name,'size_bytes':p.stat().st_size} for p in target_dir.glob('*.jar') if p.is_file() and not p.is_symlink()][:200]}
    finally:
        if was_running:
            container.start()


def reconfigure_server_allocations(client, server_id, container, payload):
    allocations = payload.get('allocations') or []
    primary = next((item for item in allocations if int(item.get('container_port', 0)) == 25565 and item.get('protocol') == 'tcp'), None)
    if primary is None or int(primary.get('port', 0)) != int(payload.get('primary_port', primary.get('port', 0))):
        if primary is None:
            raise ValueError('Primary Minecraft allocation is missing')
    extra = [item for item in allocations if item is not primary]
    if len(extra) > 10:
        raise ValueError('Too many additional allocations')
    _, mountpoint = server_volume(client, server_id)
    was_running = container.status == 'running'
    if was_running:
        container.stop(timeout=30)
    try:
        container.remove(v=False)
        replacement = create_minecraft_container(client, server_id, str(payload.get('version','LATEST')),
            int(payload.get('memory_mb',1024)), float(payload.get('cpu_limit',1)),
            int(primary['port']), str(payload.get('server_type','paper')), extra)
        if not was_running:
            replacement.stop(timeout=30)
        return {'docker_id':replacement.id,'data':{'status':'online' if was_running else 'offline','allocations':len(allocations)}}
    except Exception:
        log.exception('Allocation reconfiguration failed for server %s', server_id)
        raise



def decrypt_node_secret(payload):
    encoded = str(payload.get('password_encrypted') or '')
    token = os.getenv('NODE_TOKEN', '')
    if len(token) < 32 or not encoded:
        raise RuntimeError('Encrypted node task credential is missing')
    try:
        raw = base64.urlsafe_b64decode(encoded.encode('ascii'))
        key = __import__('hashlib').sha256(token.encode('utf-8')).digest()
        return AESGCM(key).decrypt(raw[:12], raw[12:], None).decode('utf-8')
    except Exception as exc:
        raise RuntimeError('Could not decrypt the node task credential; check node token synchronization') from exc


def ensure_sftp_network(client, server_id):
    name = f'lighting-sftp-net-{int(server_id)}'
    try:
        network = client.networks.get(name)
    except docker.errors.NotFound:
        network = client.networks.create(name, driver='bridge',
            labels={LABEL_OWNER:'true','net.lightingpanel.sftp-server-id':str(server_id)})
    labels = network.attrs.get('Labels', {}) or {}
    if labels.get(LABEL_OWNER) != 'true' or labels.get('net.lightingpanel.sftp-server-id') != str(server_id):
        raise RuntimeError('SFTP network ownership validation failed')
    return network

def run_sftp_task(client, action, payload, server_id):
    name = f'lighting-sftp-{int(server_id)}'
    config_volume = f'lighting-sftp-config-{int(server_id)}'
    if action == 'sftp_delete':
        try:
            container = client.containers.get(name)
            if container.labels.get(LABEL_OWNER) != 'true' or container.labels.get('net.lightingpanel.sftp-server-id') != str(server_id):
                raise RuntimeError('Refusing to remove an unmanaged SFTP container')
            container.remove(force=True)
        except docker.errors.NotFound:
            pass
        try:
            volume = client.volumes.get(config_volume)
            if volume.attrs.get('Labels', {}).get(LABEL_OWNER) == 'true':
                volume.remove(force=False)
        except docker.errors.NotFound:
            pass
        try:
            network = client.networks.get(f'lighting-sftp-net-{server_id}')
            if network.attrs.get('Labels',{}).get(LABEL_OWNER) == 'true' and network.attrs.get('Labels',{}).get('net.lightingpanel.sftp-server-id') == str(server_id):
                network.remove()
        except docker.errors.NotFound:
            pass
        return {'data':{'status':'removed'}}
    if action != 'sftp_create':
        raise ValueError('Unsupported SFTP operation')
    server_volume(client, server_id)
    port = int(payload.get('port',0))
    username = str(payload.get('username',''))
    password = decrypt_node_secret(payload)
    if not 31000 <= port <= 31999 or not __import__('re').fullmatch(r'lpgp[0-9]{1,10}',username) or len(password) < 32:
        raise ValueError('SFTP provisioning parameters are invalid')
    try:
        existing = client.containers.get(name)
        if existing.labels.get(LABEL_OWNER) != 'true' or existing.labels.get('net.lightingpanel.sftp-server-id') != str(server_id):
            raise RuntimeError('SFTP container name collision; refusing to modify an unmanaged container')
        existing.remove(force=True)
    except docker.errors.NotFound:
        pass
    try:
        old_config = client.volumes.get(config_volume)
        if old_config.attrs.get('Labels',{}).get(LABEL_OWNER) == 'true' and old_config.attrs.get('Labels',{}).get('net.lightingpanel.sftp-server-id') == str(server_id):
            old_config.remove(force=False)
    except docker.errors.NotFound:
        pass
    client.volumes.create(name=config_volume,labels={LABEL_OWNER:'true','net.lightingpanel.sftp-server-id':str(server_id)})
    sftp_network = ensure_sftp_network(client, server_id)
    admin_user = 'lpgp-admin'
    admin_password = __import__('hashlib').sha256((os.getenv('NODE_TOKEN','') + ':lpgp-sftp-admin:' + str(server_id)).encode()).hexdigest()
    container = client.containers.run(
        'drakkan/sftpgo:latest',name=name,detach=True,
        environment={
            'SFTPGO_DEFAULT_ADMIN_USERNAME':admin_user,
            'SFTPGO_DEFAULT_ADMIN_PASSWORD':admin_password,
            'SFTPGO_DATA_PROVIDER__CREATE_DEFAULT_ADMIN':'true',
            'SFTPGO_HTTPD__BINDINGS__0__ADDRESS':'0.0.0.0',
            'SFTPGO_HTTPD__BINDINGS__0__PORT':'8080',
            'SFTPGO_SFTPD__BINDINGS__0__ADDRESS':'0.0.0.0',
            'SFTPGO_SFTPD__BINDINGS__0__PORT':'2022',
            'SFTPGO_LOG_LEVEL':'info',
        },
        ports={'2022/tcp':('0.0.0.0',port)},network=sftp_network.name,
        volumes={f'lighting-server-data-{server_id}':{'bind':'/srv/sftpgo/data','mode':'rw'},
                 config_volume:{'bind':'/var/lib/sftpgo','mode':'rw'}},
        labels={LABEL_OWNER:'true','net.lightingpanel.sftp-server-id':str(server_id)},
        restart_policy={'Name':'unless-stopped'},pids_limit=256,
        cap_drop=['NET_RAW','SYS_CHROOT','MKNOD'],security_opt=['no-new-privileges:true'])
    try:
        for _ in range(30):
            container.reload()
            networks = container.attrs.get('NetworkSettings',{}).get('Networks',{}) or {}
            ip = next((item.get('IPAddress') for item in networks.values() if item.get('IPAddress')), '')
            if ip:
                try:
                    token_response = requests.get(f'http://{ip}:8080/api/v2/token',auth=(admin_user,admin_password),timeout=(2,4))
                    if token_response.ok:
                        access_token = token_response.json().get('access_token')
                        if access_token:
                            user_response = requests.post(f'http://{ip}:8080/api/v2/users',
                                headers={'Authorization':'Bearer '+access_token},
                                json={'username':username,'password':password,'home_dir':'/srv/sftpgo/data',
                                      'permissions':{'/':['*']},'status':1,'uid':1000,'gid':1000},
                                timeout=(3,10))
                            user_response.raise_for_status()
                            return {'data':{'status':'active','port':port,'username':username}}
                except requests.RequestException:
                    pass
            time.sleep(1)
        raise RuntimeError('SFTPGo API did not become ready or could not create the SFTP account')
    except Exception:
        try:
            container.remove(force=True)
        except Exception:
            pass
        raise



def wait_for_container_port(container, network, port, attempts=45):
    for _ in range(attempts):
        container.reload()
        if container.status != 'running':
            time.sleep(1)
            continue
        networks = container.attrs.get('NetworkSettings',{}).get('Networks',{}) or {}
        address = (networks.get(network.name) or {}).get('IPAddress')
        if address:
            try:
                with socket.create_connection((address, int(port)), timeout=2):
                    return True
            except OSError:
                pass
        time.sleep(1)
    raise RuntimeError(f'Managed service did not open its internal TCP port {port} in time')

def run_database_task(client, action, payload, server_id, server_container):
    database_id = int(payload.get('database_id', 0))
    if database_id <= 0:
        raise ValueError('Database task has no valid database id')
    name = f'lighting-db-{database_id}'
    volume_name = f'lighting-db-data-{database_id}'
    if action == 'database_delete':
        try:
            container = client.containers.get(name)
            if container.labels.get(LABEL_OWNER) != 'true' or container.labels.get('net.lightingpanel.database-id') != str(database_id):
                raise RuntimeError('Refusing to remove an unmanaged database container')
            container.remove(force=True)
        except docker.errors.NotFound:
            pass
        try:
            volume = client.volumes.get(volume_name)
            if volume.attrs.get('Labels',{}).get(LABEL_OWNER) == 'true' and volume.attrs.get('Labels',{}).get('net.lightingpanel.database-id') == str(database_id):
                volume.remove(force=False)
        except docker.errors.NotFound:
            pass
        return {'data':{'status':'removed'}}
    network = ensure_server_network(client, server_id)
    server_container.reload()
    connected = server_container.attrs.get('NetworkSettings',{}).get('Networks',{}) or {}
    if network.name not in connected:
        network.connect(server_container, aliases=[f'lighting-server-{server_id}'])
    if 'bridge' in connected:
        try:
            client.networks.get('bridge').disconnect(server_container, force=True)
        except docker.errors.APIError:
            pass
    db_type = str(payload.get('db_type',''))
    database_name = str(payload.get('database_name',''))
    username = str(payload.get('username',''))
    password = decrypt_node_secret(payload)
    port = int(payload.get('port',0))
    if db_type not in ('mariadb','postgres') or not __import__('re').fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,47}',database_name) or not __import__('re').fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,31}',username):
        raise ValueError('Database type, name, or username is invalid')
    if not 32000 <= port <= 32999 or len(password) < 40:
        raise ValueError('Database port or password is invalid')
    try:
        existing = client.containers.get(name)
        if existing.labels.get(LABEL_OWNER) != 'true' or existing.labels.get('net.lightingpanel.database-id') != str(database_id) or existing.labels.get('net.lightingpanel.server-id') != str(server_id):
            raise RuntimeError('Database container name collision; refusing to modify an unmanaged container')
        existing.reload()
        db_networks = existing.attrs.get('NetworkSettings',{}).get('Networks',{}) or {}
        if network.name not in db_networks:
            network.connect(existing, aliases=[name])
        internal_port = 3306 if db_type == 'mariadb' else 5432
        wait_for_container_port(existing, network, internal_port)
        return {'data':{'status':'active','internal_host':name,'internal_port':internal_port}}
    except docker.errors.NotFound:
        pass
    db_volume = client.volumes.create(name=volume_name,labels={LABEL_OWNER:'true','net.lightingpanel.database-id':str(database_id),'net.lightingpanel.server-id':str(server_id)})
    if db_volume.attrs.get('Labels',{}).get(LABEL_OWNER) != 'true' or db_volume.attrs.get('Labels',{}).get('net.lightingpanel.database-id') != str(database_id):
        raise RuntimeError('Database volume ownership validation failed')
    env = {'MARIADB_DATABASE':database_name,'MARIADB_USER':username,'MARIADB_PASSWORD':password,'MARIADB_ROOT_PASSWORD':secrets.token_urlsafe(36)} if db_type == 'mariadb' else {'POSTGRES_DB':database_name,'POSTGRES_USER':username,'POSTGRES_PASSWORD':password}
    image = 'mariadb:11.4' if db_type == 'mariadb' else 'postgres:16-alpine'
    internal_port = 3306 if db_type == 'mariadb' else 5432
    container = client.containers.run(
        image,name=name,detach=True,environment=env,
        ports={f'{internal_port}/tcp':('0.0.0.0',port)},
        volumes={volume_name:{'bind':'/var/lib/mysql' if db_type == 'mariadb' else '/var/lib/postgresql/data','mode':'rw'}},
        network=network.name,mem_limit='384m',nano_cpus=250000000,pids_limit=256,
        labels={LABEL_OWNER:'true','net.lightingpanel.database-id':str(database_id),'net.lightingpanel.server-id':str(server_id)},
        restart_policy={'Name':'unless-stopped'},cap_drop=['NET_RAW','SYS_CHROOT','MKNOD'],
        security_opt=['no-new-privileges:true'])
    wait_for_container_port(container, network, internal_port)
    return {'data':{'status':'active','internal_host':name,'internal_port':internal_port,'docker_id':container.id}}


def cleanup_server_resources(client, server_id):
    server_id = str(int(server_id))
    for container in client.containers.list(all=True):
        labels = container.labels or {}
        belongs = labels.get('net.lightingpanel.server-id') == server_id or labels.get('net.lightingpanel.sftp-server-id') == server_id
        if belongs and labels.get(LABEL_OWNER) == 'true':
            try:
                container.remove(force=True)
            except docker.errors.NotFound:
                pass
    for volume in client.volumes.list():
        labels = volume.attrs.get('Labels',{}) or {}
        belongs = labels.get('net.lightingpanel.server-id') == server_id or labels.get('net.lightingpanel.sftp-server-id') == server_id
        if belongs and labels.get(LABEL_OWNER) == 'true':
            try:
                volume.remove(force=False)
            except docker.errors.APIError as exc:
                log.warning('Could not remove managed volume %s for server %s: %s',volume.name,server_id,exc)
    for network_name, label_key in ((f'lighting-server-net-{server_id}','net.lightingpanel.server-id'),(f'lighting-sftp-net-{server_id}','net.lightingpanel.sftp-server-id')):
        try:
            network = client.networks.get(network_name)
            labels = network.attrs.get('Labels',{}) or {}
            if labels.get(LABEL_OWNER) == 'true' and labels.get(label_key) == server_id:
                network.remove()
        except docker.errors.NotFound:
            pass
    return {'docker_id':None}

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
        server_type = str(payload.get('server_type', 'paper')).lower()
        if server_type not in ('paper','fabric','forge'):
            raise ValueError('Unsupported Minecraft server type')
        if not 512 <= memory_mb <= 16384 or not 0.5 <= cpu_limit <= 16 or not 25565 <= port <= 25999:
            raise ValueError('Server resource or port values are outside allowed limits')
        try:
            existing = client.containers.get(name)
            if existing.labels.get(LABEL_OWNER) != 'true' or existing.labels.get('net.lightingpanel.server-id') != str(server_id):
                raise RuntimeError('Container name collision; refusing to modify an unmanaged container')
            if existing.status != 'running':
                existing.start()
            network = ensure_server_network(client, server_id)
            existing.reload()
            connected = existing.attrs.get('NetworkSettings',{}).get('Networks',{}) or {}
            if network.name not in connected:
                network.connect(existing, aliases=[f'lighting-server-{server_id}'])
            if 'bridge' in connected:
                try:
                    client.networks.get('bridge').disconnect(existing, force=True)
                except docker.errors.APIError:
                    pass
            return {'docker_id': existing.id}
        except docker.errors.NotFound:
            pass
        volume = f'lighting-server-data-{server_id}'
        client.volumes.create(name=volume, labels={LABEL_OWNER:'true','net.lightingpanel.server-id':str(server_id)})
        container = create_minecraft_container(client, server_id, version, memory_mb, cpu_limit, port, server_type)
        return {'docker_id':container.id}
    try:
        container = client.containers.get(name)
    except docker.errors.NotFound:
        if action == 'delete':
            return cleanup_server_resources(client, server_id)
        if action == 'sftp_delete':
            return run_sftp_task(client, action, payload, server_id)
        if action == 'database_delete':
            return run_database_task(client, action, payload, server_id, None)
        raise RuntimeError('Managed server container does not exist')
    if container.labels.get(LABEL_OWNER) != 'true' or container.labels.get('net.lightingpanel.server-id') != str(server_id):
        raise RuntimeError('Refusing to operate on a container not owned by Lighting Panel')
    if action in ('sftp_create','sftp_delete'):
        return run_sftp_task(client, action, payload, server_id)
    if action in ('database_create','database_delete'):
        return run_database_task(client, action, payload, server_id, container)
    if action == 'allocation_update':
        return reconfigure_server_allocations(client, server_id, container, payload)
    if action == 'mod_manager':
        return {'data':run_mod_manager(client, server_id, container, payload)}
    if action in ('backup_create','backup_list','backup_restore'):
        return {'data':run_backup_task(client, action, payload, server_id, container)}
    if action == 'version_upgrade':
        result = upgrade_minecraft_server(client, server_id, container, payload)
        return {'docker_id':result['docker_id'],'data':result}
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
        return cleanup_server_resources(client, server_id)
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
