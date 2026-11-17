from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default='user', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    audit_events: Mapped[list['AuditEvent']] = relationship(back_populates='actor')

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, default='', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    actor: Mapped[User | None] = relationship(back_populates='audit_events')

class Node(Base):
    __tablename__ = 'nodes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    fqdn: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cpu_percent: Mapped[float] = mapped_column(default=0, nullable=False)
    memory_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disk_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disk_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class GameServer(Base):
    __tablename__ = 'game_servers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    name: Mapped[str] = mapped_column(String(48), nullable=False)
    game: Mapped[str] = mapped_column(String(24), default='minecraft', nullable=False)
    version: Mapped[str] = mapped_column(String(24), default='LATEST', nullable=False)
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    cpu_limit: Mapped[float] = mapped_column(default=1.0, nullable=False)
    allocation_port: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='installing', nullable=False)
    docker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class NodeTask(Base):
    __tablename__ = 'node_tasks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False, index=True)
    server_id: Mapped[int | None] = mapped_column(ForeignKey('game_servers.id', ondelete='SET NULL'), nullable=True)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[str] = mapped_column(Text, default='{}', nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='pending', nullable=False, index=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
