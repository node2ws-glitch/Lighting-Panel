from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from app.config import get_settings

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash('not-a-real-user-password')

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)

def create_access_token(user_id: int) -> tuple[str, int]:
    settings = get_settings()
    expires = settings.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': str(user_id), 'iat': now, 'exp': now + timedelta(seconds=expires), 'type': 'access'}, settings.secret_key, algorithm='HS256')
    return token, expires

def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, get_settings().secret_key, algorithms=['HS256'], options={'require': ['sub', 'exp', 'iat']})
    if payload.get('type') != 'access':
        raise jwt.InvalidTokenError('Wrong token type')
    return int(payload['sub'])
