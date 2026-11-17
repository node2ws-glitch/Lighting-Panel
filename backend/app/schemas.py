from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(default='user', pattern=r'^(user|admin)$')

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    username: str
    role: str
    is_active: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    user: UserRead

class MessageResponse(BaseModel):
    message: str

class NodeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80, pattern=r'^[a-zA-Z0-9_.-]+$')
    fqdn: str = Field(min_length=3, max_length=255)

class NodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    fqdn: str
    is_enabled: bool
    cpu_percent: float
    memory_total: int
    memory_used: int
    disk_total: int
    disk_used: int
    last_heartbeat: datetime | None

class NodeHeartbeat(BaseModel):
    cpu_percent: float = Field(ge=0, le=100)
    memory_total: int = Field(ge=0)
    memory_used: int = Field(ge=0)
    disk_total: int = Field(ge=0)
    disk_used: int = Field(ge=0)
