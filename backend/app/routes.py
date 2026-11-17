import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.audit import record_event
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import AuditEvent, Node, User
from app.schemas import LoginRequest, MessageResponse, NodeCreate, NodeHeartbeat, NodeRead, TokenResponse, UserCreate, UserRead
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
