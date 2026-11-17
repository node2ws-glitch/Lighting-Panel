from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import require_admin
from app.models import GameServer, Node, NodeTask, User
from datetime import datetime, timedelta, timezone

router=APIRouter(tags=['operations'])

@router.get('/health/live')
def liveness():
    return {'status':'alive'}

@router.get('/health/ready')
def readiness(db: Session=Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        raise HTTPException(status_code=503,detail='Database is unavailable')
    return {'status':'ready','database':'connected'}

@router.get('/admin/metrics')
def metrics(_: User=Depends(require_admin), db: Session=Depends(get_db)):
    now=datetime.now(timezone.utc)
    recent=now-timedelta(seconds=90)
    nodes=list(db.scalars(select(Node)).all())
    online=sum(1 for node in nodes if node.last_heartbeat and (node.last_heartbeat.replace(tzinfo=timezone.utc) if node.last_heartbeat.tzinfo is None else node.last_heartbeat)>=recent and node.is_enabled)
    return {
        'servers':{
            'total':db.scalar(select(func.count(GameServer.id))) or 0,
            'online':db.scalar(select(func.count(GameServer.id)).where(GameServer.status=='online')) or 0,
            'error':db.scalar(select(func.count(GameServer.id)).where(GameServer.status=='error')) or 0,
        },
        'nodes':{'total':len(nodes),'online':online,'offline':len(nodes)-online},
        'tasks':{
            'pending':db.scalar(select(func.count(NodeTask.id)).where(NodeTask.status=='pending')) or 0,
            'claimed':db.scalar(select(func.count(NodeTask.id)).where(NodeTask.status=='claimed')) or 0,
            'failed':db.scalar(select(func.count(NodeTask.id)).where(NodeTask.status=='failed')) or 0,
        },
        'users':{'active':db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0},
        'generated_at':now,
    }
