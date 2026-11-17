from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.audit import record_event
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import AuditEvent, User
from app.schemas import LoginRequest, MessageResponse, TokenResponse, UserCreate, UserRead
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
