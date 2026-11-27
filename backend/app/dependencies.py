import jwt
import hashlib
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ApiKey
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required', headers={'WWW-Authenticate': 'Bearer'})
    if credentials is None:
        raise unauthorized
    credential = credentials.credentials
    api_key = None
    if credential.startswith('lpgp_'):
        digest = hashlib.sha256(credential.encode()).hexdigest()
        api_key = db.query(ApiKey).filter(ApiKey.token_hash == digest, ApiKey.revoked_at.is_(None)).first()
        if api_key is None or (api_key.expires_at is not None and (api_key.expires_at.replace(tzinfo=timezone.utc) if api_key.expires_at.tzinfo is None else api_key.expires_at) <= datetime.now(timezone.utc)):
            raise unauthorized
        user_id = api_key.user_id
        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
    else:
        try:
            user_id = decode_access_token(credential)
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    if api_key is not None:
        user._api_key_read_only = True
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if getattr(user, '_api_key_read_only', False) or user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Administrator permission required')
    return user
