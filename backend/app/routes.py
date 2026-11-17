import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.audit import record_event
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import AuditEvent, GameServer, Node, NodeTask, User, ServerSubuser
from app.schemas import LoginRequest, MessageResponse, NodeCreate, NodeHeartbeat, NodeRead, NodeTaskResult, ServerAction, ServerCreate, ServerRead, TokenResponse, UserCreate, UserRead, ConsoleCommand, ServerFileRequest, MinecraftAction, BackupAction, VersionUpgrade, ServerMemberCreate
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter()

@router.post('/auth/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')
    token, expires = create_access_token(user.id)
    record_event(db, 'auth.login', user, 'Successful sign-in')
    db.commit()
    return TokenResponse(access_token=token, expires_in=expires, user=user)

@router.get('/auth/me', response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user

@router.post('/auth/logout', response_model=MessageResponse)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record_event(db, 'auth.logout', user, 'Client discarded its short-lived access token')
    db.commit()
    return MessageResponse(message='Signed out. Discard the access token on the client.')

@router.get('/admin/users', response_model=list[UserRead])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.created_at.desc()).limit(500)).all())

@router.post('/admin/users', response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User.id).where((User.email == email) | (User.username == payload.username))):
        raise HTTPException(status_code=409, detail='Email or username is already in use')
    user = User(email=email, username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    record_event(db, 'admin.user.create', actor, f'Created {email} with role {payload.role}')
    db.commit()
    db.refresh(user)
    return user

@router.patch('/admin/users/{user_id}/status', response_model=UserRead)
def set_user_status(user_id: int, is_active: bool, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail='User not found')
    if user.id == actor.id and not is_active:
        raise HTTPException(status_code=400, detail='You cannot deactivate your own account')
    user.is_active = is_active
    record_event(db, 'admin.user.status', actor, f'Set user {user.email} active={is_active}')
    db.commit()
    db.refresh(user)
    return user

@router.get('/admin/audit', response_model=list[dict])
def list_audit(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(AuditEvent.id, AuditEvent.actor_id, AuditEvent.action, AuditEvent.detail, AuditEvent.created_at).order_by(AuditEvent.created_at.desc()).limit(200)).mappings().all()
    return [dict(row) for row in rows]

@router.get('/health', response_model=MessageResponse)
def health():
    return MessageResponse(message='Lighting Panel API is healthy')

@router.get('/admin/nodes', response_model=list[NodeRead])
def list_nodes(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(Node).order_by(Node.created_at.desc())).all())

@router.post('/admin/nodes', status_code=status.HTTP_201_CREATED)
def create_node(payload: NodeCreate, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Node.id).where(Node.name == payload.name)):
        raise HTTPException(status_code=409, detail='Node name already exists')
    token = secrets.token_urlsafe(48)
    node = Node(name=payload.name, fqdn=payload.fqdn, token_hash=hashlib.sha256(token.encode()).hexdigest())
    db.add(node)
    record_event(db, 'admin.node.create', actor, f'Created node {payload.name} ({payload.fqdn})')
    db.commit()
    db.refresh(node)
    return {'node': NodeRead.model_validate(node), 'token': token}

@router.post('/nodes/heartbeat', response_model=NodeRead)
def node_heartbeat(payload: NodeHeartbeat, x_node_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not x_node_token:
        raise HTTPException(status_code=401, detail='Node token required')
    token_hash = hashlib.sha256(x_node_token.encode()).hexdigest()
    node = db.scalar(select(Node).where(Node.token_hash == token_hash))
    if node is None or not node.is_enabled:
        raise HTTPException(status_code=401, detail='Invalid or disabled node credential')
    if payload.memory_used > payload.memory_total or payload.disk_used > payload.disk_total:
        raise HTTPException(status_code=422, detail='Used resource values cannot exceed totals')
    node.cpu_percent = payload.cpu_percent
    node.memory_total = payload.memory_total
    node.memory_used = payload.memory_used
    node.disk_total = payload.disk_total
    node.disk_used = payload.disk_used
    node.last_heartbeat = datetime.now(timezone.utc)
    db.commit()
    db.refresh(node)
    return node

@router.patch('/admin/nodes/{node_id}/status', response_model=NodeRead)
def set_node_status(node_id: int, is_enabled: bool, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail='Node not found')
    node.is_enabled = is_enabled
    record_event(db, 'admin.node.status', actor, f'Set node {node.name} enabled={is_enabled}')
    db.commit()
    db.refresh(node)
    return node

def node_is_recent(node: Node) -> bool:
    if node.last_heartbeat is None:
        return False
    stamp = node.last_heartbeat
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - stamp).total_seconds() <= 90

def authenticate_node(x_node_token: str | None, db: Session) -> Node:
    if not x_node_token:
        raise HTTPException(status_code=401, detail='Node token required')
    digest = hashlib.sha256(x_node_token.encode()).hexdigest()
    node = db.scalar(select(Node).where(Node.token_hash == digest))
    if node is None or not node.is_enabled:
        raise HTTPException(status_code=401, detail='Invalid or disabled node credential')
    return node

@router.get('/admin/servers', response_model=list[ServerRead])
def list_servers(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(GameServer).order_by(GameServer.created_at.desc()).limit(500)
    if actor.role != 'admin':
        query = select(GameServer).outerjoin(ServerSubuser, ServerSubuser.server_id == GameServer.id).where(or_(GameServer.owner_id == actor.id, (ServerSubuser.user_id == actor.id) & ServerSubuser.permissions.contains('"server.read"'))).order_by(GameServer.created_at.desc()).limit(500)
    return list(db.scalars(query).unique().all())

@router.post('/admin/servers', response_model=ServerRead, status_code=status.HTTP_202_ACCEPTED)
def create_server(payload: ServerCreate, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    node = db.get(Node, payload.node_id)
    if node is None or not node.is_enabled:
        raise HTTPException(status_code=400, detail='Choose an enabled node')
    if not node_is_recent(node):
        raise HTTPException(status_code=409, detail='Node is offline or has no recent heartbeat')
    if payload.memory_mb * 1024 * 1024 > node.memory_total - node.memory_used:
        raise HTTPException(status_code=409, detail='Node does not have enough reported free memory')
    used = db.scalars(select(GameServer.allocation_port)).all()
    port = next((p for p in range(25565, 26000) if p not in set(used)), None)
    if port is None:
        raise HTTPException(status_code=409, detail='No free Minecraft allocations remain')
    owner = actor
    if payload.owner_email:
        owner = db.scalar(select(User).where(User.email == str(payload.owner_email).lower(), User.is_active.is_(True)))
        if owner is None or owner.role == 'admin':
            raise HTTPException(status_code=400, detail='Choose an active customer account, not an administrator')
    server = GameServer(node_id=node.id, owner_id=owner.id, name=payload.name.strip(), version=payload.version,
        memory_mb=payload.memory_mb, cpu_limit=payload.cpu_limit, allocation_port=port, status='installing')
    db.add(server)
    db.flush()
    task = NodeTask(node_id=node.id, server_id=server.id, action='provision',
        payload=json.dumps({'server_id':server.id,'name':server.name,'version':server.version,'memory_mb':server.memory_mb,'cpu_limit':server.cpu_limit,'port':server.allocation_port}))
    db.add(task)
    record_event(db, 'admin.server.create', actor, f'Queued server {server.id} on node {node.name}')
    db.commit()
    db.refresh(server)
    return server

@router.post('/admin/servers/{server_id}/action', response_model=ServerRead, status_code=status.HTTP_202_ACCEPTED)
def server_action(server_id: int, payload: ServerAction, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission = {'start':'control.start','stop':'control.stop','restart':'control.restart','delete':'server.manage'}[payload.action]
    server = require_server_permission(server_id, actor, permission, db)
    if payload.action == 'delete' and actor.role != 'admin' and server.owner_id != actor.id:
        raise HTTPException(status_code=403, detail='Only the server owner can delete this server')
    node = db.get(Node, server.node_id)
    if node is None or not node.is_enabled or not node_is_recent(node):
        raise HTTPException(status_code=409, detail='Server node is offline')
    if server.status == 'installing':
        raise HTTPException(status_code=409, detail='Server provisioning is still in progress')
    if payload.action == 'delete':
        server.status = 'deleting'
    elif payload.action in ('start','restart'):
        server.status = 'starting'
    else:
        server.status = 'stopping'
    db.add(NodeTask(node_id=node.id, server_id=server.id, action=payload.action, payload=json.dumps({'server_id':server.id})))
    record_event(db, 'admin.server.'+payload.action, actor, f'Queued {payload.action} for server {server.id}')
    db.commit()
    db.refresh(server)
    return server

@router.get('/nodes/tasks')
def claim_node_tasks(x_node_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    node = authenticate_node(x_node_token, db)
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=2)
    stale_tasks = db.scalars(select(NodeTask).where(NodeTask.node_id == node.id, NodeTask.status == 'claimed', NodeTask.claimed_at < stale_before)).all()
    for stale in stale_tasks:
        stale.status = 'pending'
        stale.claimed_at = None
    tasks = list(db.scalars(select(NodeTask).where(NodeTask.node_id == node.id, NodeTask.status == 'pending').order_by(NodeTask.id).limit(5)).all())
    output = []
    for task in tasks:
        task.status = 'claimed'
        task.claimed_at = now
        output.append({'id':task.id,'server_id':task.server_id,'action':task.action,'payload':json.loads(task.payload)})
    db.commit()
    return output

@router.post('/nodes/tasks/{task_id}/result')
def finish_node_task(task_id: int, payload: NodeTaskResult, x_node_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    node = authenticate_node(x_node_token, db)
    task = db.get(NodeTask, task_id)
    if task is None or task.node_id != node.id or task.status != 'claimed':
        raise HTTPException(status_code=404, detail='Claimed task not found')
    task.status = 'failed' if payload.error else 'completed'
    task.result = json.dumps({'docker_id':payload.docker_id,'error':payload.error,'data':payload.data})
    task.completed_at = datetime.now(timezone.utc)
    if task.server_id and task.action in ('provision','start','stop','restart','delete','version_upgrade'):
        server = db.get(GameServer, task.server_id)
        if server:
            server.docker_id = payload.docker_id or server.docker_id
            server.last_error = payload.error
            if task.action == 'delete' and not payload.error:
                db.delete(server)
            elif payload.error:
                server.status = 'error'
            elif task.action == 'stop':
                server.status = 'offline'
            elif task.action == 'version_upgrade' and not payload.error:
                server.version = json.loads(task.payload).get('version', server.version)
                server.status = 'online'
            else:
                server.status = 'online'
    db.commit()
    return {'accepted':True}


def server_permissions(server: GameServer, actor: User, db: Session) -> set[str]:
    if actor.role == 'admin' or server.owner_id == actor.id:
        return {'server.read','control.console','control.start','control.stop','control.restart','file.read','file.write','backup.read','backup.create','backup.restore','server.manage'}
    membership = db.scalar(select(ServerSubuser).where(ServerSubuser.server_id == server.id, ServerSubuser.user_id == actor.id))
    return set(json.loads(membership.permissions)) if membership else set()

def require_server_permission(server_id: int, actor: User, permission: str, db: Session) -> GameServer:
    server = db.get(GameServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    if permission not in server_permissions(server, actor, db):
        raise HTTPException(status_code=403, detail='You do not have permission to perform this action')
    return server

def task_permission(task: NodeTask) -> str:
    if task.action in ('console','console_logs'):
        return 'control.console'
    if task.action in ('file_list','file_read'):
        return 'file.read'
    if task.action.startswith('file_'):
        return 'file.write'
    if task.action == 'backup_list':
        return 'backup.read'
    if task.action == 'backup_create':
        return 'backup.create'
    if task.action == 'backup_restore':
        return 'backup.restore'
    if task.action == 'version_upgrade':
        return 'server.manage'
    return 'server.read'

def get_managed_server(server_id: int, db: Session, actor: User, permission: str) -> tuple[GameServer, Node]:
    server = require_server_permission(server_id, actor, permission, db)
    node = db.get(Node, server.node_id)
    if node is None or not node.is_enabled or not node_is_recent(node):
        raise HTTPException(status_code=409, detail='Server node is offline')
    if server.status != 'online':
        raise HTTPException(status_code=409, detail='Server must be online before using console or files')
    return server, node

@router.post('/admin/servers/{server_id}/console', status_code=status.HTTP_202_ACCEPTED)
def send_console_command(server_id: int, payload: ConsoleCommand, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server, node = get_managed_server(server_id, db, actor, 'control.console')
    command = payload.command.strip()
    if not command or command.startswith('/') or len(command) > 512 or any(ord(ch) < 32 for ch in command):
        raise HTTPException(status_code=422, detail='Enter a valid Minecraft command without the leading slash')
    task = NodeTask(node_id=node.id, server_id=server.id, action='console', payload=json.dumps({'server_id':server.id,'command':command}))
    db.add(task)
    record_event(db, 'admin.server.console', actor, f'Sent console command to server {server.id}')
    db.commit()
    db.refresh(task)
    return {'task_id':task.id,'status':task.status}

@router.post('/admin/servers/{server_id}/console/logs', status_code=status.HTTP_202_ACCEPTED)
def request_console_logs(server_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server, node = get_managed_server(server_id, db, actor, 'control.console')
    latest = db.scalar(select(NodeTask).where(NodeTask.server_id == server.id, NodeTask.action == 'console_logs').order_by(NodeTask.id.desc()).limit(1))
    if latest and latest.status in ('pending','claimed'):
        return {'task_id':latest.id,'status':latest.status}
    if latest and latest.completed_at:
        stamp = latest.completed_at.replace(tzinfo=timezone.utc) if latest.completed_at.tzinfo is None else latest.completed_at
        if (datetime.now(timezone.utc)-stamp).total_seconds() < 2:
            return {'task_id':latest.id,'status':latest.status}
    task = NodeTask(node_id=node.id, server_id=server.id, action='console_logs', payload=json.dumps({'server_id':server.id}))
    db.add(task)
    db.commit()
    db.refresh(task)
    return {'task_id':task.id,'status':task.status}

@router.post('/admin/servers/{server_id}/files', status_code=status.HTTP_202_ACCEPTED)
def operate_server_files(server_id: int, payload: ServerFileRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission = 'file.read' if payload.operation in ('list','read') else 'file.write'
    server, node = get_managed_server(server_id, db, actor, permission)
    if payload.operation == 'write' and payload.content_base64 is None:
        raise HTTPException(status_code=422, detail='File content is required')
    if payload.operation == 'rename' and not payload.destination:
        raise HTTPException(status_code=422, detail='Destination path is required')
    task_payload = {'server_id':server.id,'operation':payload.operation,'path':payload.path,'destination':payload.destination,'content_base64':payload.content_base64}
    task = NodeTask(node_id=node.id, server_id=server.id, action='file_'+payload.operation, payload=json.dumps(task_payload))
    db.add(task)
    record_event(db, 'admin.server.files.'+payload.operation, actor, f'Queued file {payload.operation} for server {server.id}')
    db.commit()
    db.refresh(task)
    return {'task_id':task.id,'status':task.status}


@router.post('/admin/servers/{server_id}/minecraft/action', status_code=status.HTTP_202_ACCEPTED)
def minecraft_action(server_id: int, payload: MinecraftAction, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server, node = get_managed_server(server_id, db, actor, 'server.manage')
    action = payload.action
    if action in ('whitelist_add', 'whitelist_remove', 'op', 'deop'):
        if not payload.player:
            raise HTTPException(status_code=422, detail='A valid Minecraft username is required')
        command = {
            'whitelist_add': 'whitelist add ' + payload.player,
            'whitelist_remove': 'whitelist remove ' + payload.player,
            'op': 'op ' + payload.player,
            'deop': 'deop ' + payload.player,
        }[action]
    elif action == 'difficulty':
        if payload.value not in ('peaceful', 'easy', 'normal', 'hard'):
            raise HTTPException(status_code=422, detail='Choose peaceful, easy, normal, or hard')
        command = 'difficulty ' + payload.value
    elif action == 'gamemode':
        if payload.value not in ('survival', 'creative', 'adventure', 'spectator'):
            raise HTTPException(status_code=422, detail='Choose a supported game mode')
        command = 'defaultgamemode ' + payload.value
    elif action == 'time':
        if payload.value not in ('day', 'noon', 'night', 'midnight'):
            raise HTTPException(status_code=422, detail='Choose day, noon, night, or midnight')
        command = 'time set ' + payload.value
    elif action == 'weather':
        if payload.value not in ('clear', 'rain', 'thunder'):
            raise HTTPException(status_code=422, detail='Choose clear, rain, or thunder')
        command = 'weather ' + payload.value
    else:
        command = {'list': 'list', 'save_all': 'save-all flush'}[action]
    task = NodeTask(node_id=node.id, server_id=server.id, action='console',
        payload=json.dumps({'server_id':server.id,'command':command}))
    db.add(task)
    record_event(db, 'admin.server.minecraft.' + action, actor, f'Queued Minecraft action for server {server.id}')
    db.commit()
    db.refresh(task)
    return {'task_id':task.id,'status':task.status,'command':command}


@router.post('/admin/servers/{server_id}/backups', status_code=status.HTTP_202_ACCEPTED)
def manage_server_backups(server_id: int, payload: BackupAction, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permission = {'list':'backup.read','create':'backup.create','restore':'backup.restore'}[payload.action]
    server, node = get_managed_server(server_id, db, actor, permission)
    if payload.action == 'restore' and not payload.backup_id:
        raise HTTPException(status_code=422, detail='Choose a backup to restore')
    task_action = {'create':'backup_create','list':'backup_list','restore':'backup_restore'}[payload.action]
    task = NodeTask(node_id=node.id, server_id=server.id, action=task_action,
        payload=json.dumps({'server_id':server.id,'backup_id':payload.backup_id}))
    db.add(task)
    record_event(db, 'admin.server.backup.'+payload.action, actor, f'Queued {payload.action} backup for server {server.id}')
    db.commit()
    db.refresh(task)
    return {'task_id':task.id,'status':task.status}

@router.post('/admin/servers/{server_id}/version', status_code=status.HTTP_202_ACCEPTED)
def upgrade_server_version(server_id: int, payload: VersionUpgrade, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server, node = get_managed_server(server_id, db, actor, 'server.manage')
    if server.game != 'minecraft':
        raise HTTPException(status_code=400, detail='Version upgrades are only available for Minecraft servers')
    if payload.version == server.version:
        raise HTTPException(status_code=409, detail='Server is already configured for this version')
    task = NodeTask(node_id=node.id, server_id=server.id, action='version_upgrade',
        payload=json.dumps({'server_id':server.id,'version':payload.version,'previous_version':server.version,
            'memory_mb':server.memory_mb,'cpu_limit':server.cpu_limit,'port':server.allocation_port}))
    db.add(task)
    record_event(db, 'admin.server.version.upgrade', actor, f'Queued Minecraft version {payload.version} for server {server.id}')
    db.commit()
    db.refresh(task)
    return {'task_id':task.id,'status':task.status,'version':payload.version}

@router.get('/admin/servers/{server_id}/tasks')
def list_server_tasks(server_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_server_permission(server_id, actor, 'server.read', db)
    server = db.get(GameServer, server_id)
    permissions = server_permissions(server, actor, db)
    tasks = db.scalars(select(NodeTask).where(NodeTask.server_id == server_id).order_by(NodeTask.id.desc()).limit(40)).all()
    output = []
    for task in reversed(tasks):
        result = json.loads(task.result) if task.result else None
        if task_permission(task) not in permissions:
            result = None
        elif result and task.action == 'file_read':
            result = {'error':result.get('error'),'data':None}
        output.append({'id':task.id,'action':task.action,'status':task.status,'result':result,'created_at':task.created_at,'completed_at':task.completed_at})
    return output

@router.get('/admin/servers/{server_id}/tasks/{task_id}')
def get_server_task(server_id: int, task_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_server_permission(server_id, actor, 'server.read', db)
    task = db.get(NodeTask, task_id)
    if task is None or task.server_id != server_id:
        raise HTTPException(status_code=404, detail='Server task not found')
    if task_permission(task) not in server_permissions(db.get(GameServer, server_id), actor, db):
        raise HTTPException(status_code=403, detail='You do not have permission to view this task result')
    return {'id':task.id,'action':task.action,'status':task.status,'result':json.loads(task.result) if task.result else None,'created_at':task.created_at,'completed_at':task.completed_at}

def require_server_owner(server_id: int, actor: User, db: Session) -> GameServer:
    server = db.get(GameServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    if actor.role != 'admin' and server.owner_id != actor.id:
        raise HTTPException(status_code=403, detail='Only the server owner can manage team access')
    return server

@router.get('/admin/servers/{server_id}/members')
def list_server_members(server_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_server_owner(server_id, actor, db)
    rows = db.execute(select(ServerSubuser, User).join(User, User.id == ServerSubuser.user_id).where(ServerSubuser.server_id == server_id).order_by(ServerSubuser.created_at.asc())).all()
    return [{'id': m.id, 'user_id': u.id, 'username': u.username, 'email': u.email, 'permissions': json.loads(m.permissions), 'created_at': m.created_at} for m, u in rows]

@router.post('/admin/servers/{server_id}/members', status_code=status.HTTP_201_CREATED)
def add_server_member(server_id: int, payload: ServerMemberCreate, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_server_owner(server_id, actor, db)
    member = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if member is None or not member.is_active:
        raise HTTPException(status_code=404, detail='An active account with this email must exist first')
    server = db.get(GameServer, server_id)
    if member.id == actor.id or member.id == server.owner_id:
        raise HTTPException(status_code=400, detail='The server owner cannot be added as a subuser')
    if member.role == 'admin':
        raise HTTPException(status_code=400, detail='Administrator accounts already have full panel access')
    if db.scalar(select(ServerSubuser).where(ServerSubuser.server_id == server_id, ServerSubuser.user_id == member.id)):
        raise HTTPException(status_code=409, detail='This account already has access to the server')
    permissions = set(payload.permissions) | {'server.read'}
    if 'file.write' in permissions:
        permissions.add('file.read')
    if 'backup.create' in permissions or 'backup.restore' in permissions:
        permissions.add('backup.read')
    permissions = sorted(permissions)
    membership = ServerSubuser(server_id=server_id, user_id=member.id, permissions=json.dumps(permissions), created_by=actor.id)
    db.add(membership)
    record_event(db, 'server.member.add', actor, 'Granted server ' + str(server_id) + ' access to user ' + str(member.id) + ': ' + ','.join(permissions))
    db.commit()
    db.refresh(membership)
    return {'id':membership.id,'user_id':member.id,'username':member.username,'email':member.email,'permissions':permissions,'created_at':membership.created_at}

@router.delete('/admin/servers/{server_id}/members/{membership_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_server_member(server_id: int, membership_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_server_owner(server_id, actor, db)
    membership = db.scalar(select(ServerSubuser).where(ServerSubuser.id == membership_id, ServerSubuser.server_id == server_id))
    if membership is None:
        raise HTTPException(status_code=404, detail='Server member not found')
    db.delete(membership)
    record_event(db, 'server.member.remove', actor, 'Revoked membership ' + str(membership_id) + ' from server ' + str(server_id))
    db.commit()

@router.get('/admin/servers/{server_id}/access')
def get_server_access(server_id: int, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.get(GameServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    if actor.role == 'admin' or server.owner_id == actor.id:
        return {'is_owner':True,'permissions':['server.read','control.console','control.start','control.stop','control.restart','file.read','file.write','backup.read','backup.create','backup.restore','server.manage']}
    membership = db.scalar(select(ServerSubuser).where(ServerSubuser.server_id == server_id, ServerSubuser.user_id == actor.id))
    if membership is None:
        raise HTTPException(status_code=403, detail='You do not have access to this server')
    return {'is_owner':False,'permissions':json.loads(membership.permissions)}
