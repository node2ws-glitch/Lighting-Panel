from datetime import datetime
from typing import Literal
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

class ServerCreate(BaseModel):
    name: str = Field(min_length=3, max_length=48, pattern=r'^[a-zA-Z0-9 _.-]+$')
    node_id: int = Field(gt=0)
    version: str = Field(default='LATEST', max_length=24, pattern=r'^(LATEST|[0-9]+\.[0-9]+(\.[0-9]+)?)$')
    memory_mb: int = Field(default=2048, ge=512, le=16384)
    cpu_limit: float = Field(default=2.0, ge=0.5, le=16)

class ServerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    node_id: int
    name: str
    game: str
    version: str
    memory_mb: int
    cpu_limit: float
    allocation_port: int
    status: str
    last_error: str | None
    created_at: datetime

class ServerAction(BaseModel):
    action: str = Field(pattern=r'^(start|stop|restart|delete)$')

class NodeTaskResult(BaseModel):
    docker_id: str | None = Field(default=None, max_length=128)
    error: str | None = Field(default=None, max_length=1000)
    data: dict | None = None

class ConsoleCommand(BaseModel):
    command: str = Field(min_length=1, max_length=512)

class ServerFileRequest(BaseModel):
    operation: Literal['list','read','write','mkdir','delete','rename']
    path: str = Field(default='.', min_length=1, max_length=512)
    destination: str | None = Field(default=None, max_length=512)
    content_base64: str | None = Field(default=None, max_length=1400000)


class MinecraftAction(BaseModel):
    action: Literal['list','whitelist_add','whitelist_remove','op','deop','difficulty','gamemode','time','weather','save_all']
    player: str | None = Field(default=None, min_length=3, max_length=16, pattern=r'^[A-Za-z0-9_]{3,16}$')
    value: str | None = Field(default=None, max_length=24)

 
class BackupAction(BaseModel):
    action: Literal['create','list','restore']
    backup_id: str | None = Field(default=None, pattern=r'^\d{8}T\d{6}Z-[a-f0-9]{10}$')

class VersionUpgrade(BaseModel):
    version: str = Field(min_length=3, max_length=16, pattern=r'^\d+\.\d+(\.\d+)?$')
