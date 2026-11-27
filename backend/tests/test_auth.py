import os
os.environ.setdefault('SECRET_KEY', 'test-only-secret-key-that-is-long-enough-123456')
os.environ.setdefault('DATABASE_URL', 'sqlite://')
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password

engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)

def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_db
client = TestClient(app)

def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        db.add(User(email='admin@example.com', username='admin', password_hash=hash_password('Correct-Horse-123!'), role='admin'))
        db.commit()

def test_login_and_me():
    response = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'})
    assert response.status_code == 200
    token = response.json()['access_token']
    assert client.get('/api/v1/auth/me', headers={'Authorization':f'Bearer {token}'}).json()['role'] == 'admin'

def test_wrong_password_rejected():
    response = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'incorrect'})
    assert response.status_code == 401

def test_admin_route_requires_admin():
    assert client.get('/api/v1/admin/users').status_code == 401
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    headers = {'Authorization':f"Bearer {login['access_token']}"}
    assert client.get('/api/v1/admin/users', headers=headers).status_code == 200


def test_node_enrollment_and_heartbeat():
    from app.models import Node
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    headers = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=headers, json={'name':'test-node','fqdn':'node.example.test'})
    assert enrolled.status_code == 201
    token = enrolled.json()['token']
    heartbeat = client.post('/api/v1/nodes/heartbeat', headers={'X-Node-Token':token}, json={
        'cpu_percent':12.5,'memory_total':1000,'memory_used':500,'disk_total':5000,'disk_used':1200
    })
    assert heartbeat.status_code == 200
    assert heartbeat.json()['cpu_percent'] == 12.5
    assert client.get('/api/v1/admin/nodes', headers=headers).json()[0]['name'] == 'test-node'

def test_minecraft_server_provisioning_and_stop_queue():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'docker-node','fqdn':'docker.example.test'})
    assert enrolled.status_code == 201
    node_token = enrolled.json()['token']
    node_headers = {'X-Node-Token':node_token}
    heartbeat = client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':8,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':100*1024**3,'disk_used':10*1024**3
    })
    assert heartbeat.status_code == 200
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Test SMP','node_id':enrolled.json()['node']['id'],'version':'1.21.4','memory_mb':2048,'cpu_limit':2
    })
    assert created.status_code == 202
    server_id = created.json()['id']
    tasks = client.get('/api/v1/nodes/tasks', headers=node_headers)
    assert tasks.status_code == 200
    assert tasks.json()[0]['action'] == 'provision'
    task_id = tasks.json()[0]['id']
    result = client.post(f'/api/v1/nodes/tasks/{task_id}/result', headers=node_headers, json={'docker_id':'fake-docker-id'})
    assert result.status_code == 200
    assert client.get('/api/v1/admin/servers', headers=admin).json()[0]['status'] == 'online'
    stopped = client.post(f'/api/v1/admin/servers/{server_id}/action', headers=admin, json={'action':'stop'})
    assert stopped.status_code == 202
    stop_task = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    assert stop_task['action'] == 'stop'
    client.post(f"/api/v1/nodes/tasks/{stop_task['id']}/result", headers=node_headers, json={'docker_id':'fake-docker-id'})
    assert client.get('/api/v1/admin/servers', headers=admin).json()[0]['status'] == 'offline'

def test_server_creation_rejects_offline_node():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'offline-node','fqdn':'offline.example.test'}).json()
    response = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Should Not Deploy','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1
    })
    assert response.status_code == 409


def test_console_and_file_tasks_are_node_scoped_and_do_not_change_server_status():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'phase-six-node','fqdn':'phase-six.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':4,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':50*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Console SMP','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1
    }).json()
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-test'})
    server_id = created['id']
    command = client.post(f'/api/v1/admin/servers/{server_id}/console', headers=admin, json={'command':'list'})
    assert command.status_code == 202
    assert client.post(f'/api/v1/admin/servers/{server_id}/console', headers=admin, json={'command':'say hello'+chr(10)+'stop'}).status_code == 422
    files = client.post(f'/api/v1/admin/servers/{server_id}/files', headers=admin, json={'operation':'list','path':'.'})
    assert files.status_code == 202
    queued = client.get('/api/v1/nodes/tasks', headers=node_headers).json()
    assert {task['action'] for task in queued} == {'console','file_list'}
    for task in queued:
        client.post(f"/api/v1/nodes/tasks/{task['id']}/result", headers=node_headers, json={'data':{'output':'ok','entries':[]}})
    assert client.get('/api/v1/admin/servers', headers=admin).json()[0]['status'] == 'online'
    history = client.get(f'/api/v1/admin/servers/{server_id}/tasks', headers=admin)
    assert history.status_code == 200
    assert history.json()[-1]['status'] == 'completed'


def test_validated_minecraft_management_actions():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'minecraft-controls','fqdn':'mc.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':2,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':50*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Controls SMP','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1
    }).json()
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-controls'})
    sid = created['id']
    valid = client.post(f'/api/v1/admin/servers/{sid}/minecraft/action', headers=admin,
        json={'action':'whitelist_add','player':'Steve_123'})
    assert valid.status_code == 202
    assert valid.json()['command'] == 'whitelist add Steve_123'
    invalid_name = client.post(f'/api/v1/admin/servers/{sid}/minecraft/action', headers=admin,
        json={'action':'op','player':'Steve; stop'})
    assert invalid_name.status_code == 422
    invalid_value = client.post(f'/api/v1/admin/servers/{sid}/minecraft/action', headers=admin,
        json={'action':'difficulty','value':'hard; stop'})
    assert invalid_value.status_code == 422
    queued = client.get('/api/v1/nodes/tasks', headers=node_headers).json()
    assert queued[-1]['payload']['command'] == 'whitelist add Steve_123'


def test_backups_and_version_upgrade_are_queued_and_validated():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'phase-eight-node','fqdn':'phase-eight.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':1,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':80*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Backup SMP','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1,'version':'1.21.4'
    }).json()
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-backup'})
    sid = created['id']
    backup = client.post(f'/api/v1/admin/servers/{sid}/backups', headers=admin, json={'action':'create'})
    assert backup.status_code == 202
    version = client.post(f'/api/v1/admin/servers/{sid}/version', headers=admin, json={'version':'1.21.1'})
    assert version.status_code == 202
    assert client.post(f'/api/v1/admin/servers/{sid}/version', headers=admin, json={'version':'bad;command'}).status_code == 422
    assert client.post(f'/api/v1/admin/servers/{sid}/backups', headers=admin, json={'action':'restore'}).status_code == 422
    queued = client.get('/api/v1/nodes/tasks', headers=node_headers).json()
    assert {task['action'] for task in queued} >= {'backup_create','version_upgrade'}


def test_server_subusers_have_only_granted_permissions_and_can_be_revoked():
    from app.models import Node, GameServer
    with TestingSession() as db:
        member = User(email='staff@example.com', username='staff', password_hash=hash_password('Staff-Password-123!'), role='user')
        db.add(member)
        db.commit()
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'subuser-node','fqdn':'subuser.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':1,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':80*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Team SMP','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1
    }).json()
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-team'})
    sid = created['id']
    grant = client.post(f'/api/v1/admin/servers/{sid}/members', headers=admin, json={
        'email':'staff@example.com','permissions':['server.read','control.console','file.read']
    })
    assert grant.status_code == 201
    assert grant.json()['permissions'] == ['control.console','file.read','server.read']
    staff_login = client.post('/api/v1/auth/login', json={'email':'staff@example.com','password':'Staff-Password-123!'}).json()
    staff = {'Authorization':f"Bearer {staff_login['access_token']}"}
    visible = client.get('/api/v1/admin/servers', headers=staff)
    assert visible.status_code == 200 and [row['id'] for row in visible.json()] == [sid]
    access = client.get(f'/api/v1/admin/servers/{sid}/access', headers=staff)
    assert access.status_code == 200 and 'control.console' in access.json()['permissions']
    assert client.post(f'/api/v1/admin/servers/{sid}/console', headers=staff, json={'command':'say hello'}).status_code == 202
    assert client.post(f'/api/v1/admin/servers/{sid}/files', headers=staff, json={'operation':'list','path':'.'}).status_code == 202
    assert client.post(f'/api/v1/admin/servers/{sid}/files', headers=staff, json={'operation':'write','path':'server.properties','content_base64':'eA=='}).status_code == 403
    assert client.post(f'/api/v1/admin/servers/{sid}/backups', headers=staff, json={'action':'create'}).status_code == 403
    assert client.get(f'/api/v1/admin/servers/{sid}/members', headers=staff).status_code == 403
    member_id = grant.json()['id']
    revoked = client.delete(f'/api/v1/admin/servers/{sid}/members/{member_id}', headers=admin)
    assert revoked.status_code == 204
    assert client.get('/api/v1/admin/servers', headers=staff).json() == []
    assert client.get(f'/api/v1/admin/servers/{sid}/access', headers=staff).status_code == 403

def test_admin_can_assign_server_to_customer_owner():
    with TestingSession() as db:
        db.add(User(email='owner@example.com', username='owner', password_hash=hash_password('Owner-Password-123!'), role='user'))
        db.commit()
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization': 'Bearer ' + login['access_token']}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'customer-owner-node','fqdn':'owner.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={'cpu_percent':1,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':80*1024**3,'disk_used':5*1024**3})
    created = client.post('/api/v1/admin/servers', headers=admin, json={'name':'Customer World','node_id':enrolled['node']['id'],'owner_email':'owner@example.com','memory_mb':1024,'cpu_limit':1})
    assert created.status_code == 202
    assert created.json()['owner_id'] is not None
    owner_login = client.post('/api/v1/auth/login', json={'email':'owner@example.com','password':'Owner-Password-123!'}).json()
    owner_headers = {'Authorization':'Bearer ' + owner_login['access_token']}
    visible = client.get('/api/v1/admin/servers', headers=owner_headers)
    assert visible.status_code == 200 and visible.json()[0]['id'] == created.json()['id']
    assert client.get('/api/v1/admin/servers/' + str(created.json()['id']) + '/access', headers=owner_headers).json()['is_owner'] is True
    assert client.post('/api/v1/admin/servers', headers=owner_headers, json={'name':'Forbidden','node_id':enrolled['node']['id']}).status_code == 403

def test_phase_ten_readiness_metrics_and_security_headers():
    response=client.get('/api/v1/health/live')
    assert response.status_code==200 and response.json()['status']=='alive'
    ready=client.get('/api/v1/health/ready')
    assert ready.status_code==200 and ready.json()['database']=='connected'
    assert response.headers.get('x-content-type-options')=='nosniff'
    assert response.headers.get('x-frame-options')=='DENY'
    login=client.post('/api/v1/auth/login',json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    headers={'Authorization':'Bearer '+login['access_token']}
    metrics=client.get('/api/v1/admin/metrics',headers=headers)
    assert metrics.status_code==200
    assert metrics.json()['servers']['total']==0
    assert metrics.json()['tasks']['pending']==0
    assert client.get('/api/v1/admin/metrics').status_code==401


def test_billing_summary_is_private_and_checkout_requires_configuration(monkeypatch):
    from types import SimpleNamespace
    import app.billing as billing
    monkeypatch.setattr(billing,'get_settings',lambda:SimpleNamespace(stripe_secret_key=None,stripe_price_id=None))
    login=client.post('/api/v1/auth/login',json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    headers={'Authorization':'Bearer '+login['access_token']}
    summary=client.get('/api/v1/billing/me',headers=headers)
    assert summary.status_code==200
    assert summary.json()['subscription']['status']=='not_subscribed'
    assert summary.json()['invoices']==[]
    assert client.get('/api/v1/billing/me').status_code==401
    checkout=client.post('/api/v1/billing/checkout',headers=headers)
    assert checkout.status_code==503


def test_stripe_webhook_signature_and_event_idempotency(monkeypatch):
    import hashlib
    import hmac
    import json
    import time
    from types import SimpleNamespace
    import app.billing as billing
    secret='whsec_test_phase_ten'
    monkeypatch.setattr(billing,'get_settings',lambda:SimpleNamespace(stripe_webhook_secret=secret))
    payload=json.dumps({'id':'evt_phase10_once','type':'customer.updated','data':{'object':{'id':'cus_test'}}},separators=(',',':')).encode()
    timestamp=int(time.time())
    digest=hmac.new(secret.encode(),str(timestamp).encode()+b'.'+payload,hashlib.sha256).hexdigest()
    signature=f't={timestamp},v1={digest}'
    first=client.post('/api/v1/billing/webhook',content=payload,headers={'Stripe-Signature':signature,'Content-Type':'application/json'})
    assert first.status_code==200 and first.json()['duplicate'] is False
    second=client.post('/api/v1/billing/webhook',content=payload,headers={'Stripe-Signature':signature,'Content-Type':'application/json'})
    assert second.status_code==200 and second.json()['duplicate'] is True
    invalid=client.post('/api/v1/billing/webhook',content=payload,headers={'Stripe-Signature':'t=1,v1=bad'})
    assert invalid.status_code==400

def test_authenticated_user_can_change_password_and_wrong_current_password_is_rejected():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    headers = {'Authorization':f"Bearer {login['access_token']}"}
    wrong = client.post('/api/v1/auth/password', headers=headers, json={
        'current_password':'incorrect','new_password':'New-Correct-Horse-456!'
    })
    assert wrong.status_code == 400
    changed = client.post('/api/v1/auth/password', headers=headers, json={
        'current_password':'Correct-Horse-123!','new_password':'New-Correct-Horse-456!'
    })
    assert changed.status_code == 200
    assert client.post('/api/v1/auth/login', json={
        'email':'admin@example.com','password':'Correct-Horse-123!'
    }).status_code == 401
    assert client.post('/api/v1/auth/login', json={
        'email':'admin@example.com','password':'New-Correct-Horse-456!'
    }).status_code == 200
    assert client.post('/api/v1/auth/password', headers=headers, json={
        'current_password':'New-Correct-Horse-456!','new_password':'short'
    }).status_code == 422
def test_admin_can_rotate_node_token_and_old_token_is_rejected():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'rotate-node','fqdn':'rotate.example.test'}).json()
    old_token = enrolled['token']
    rotated = client.post(f"/api/v1/admin/nodes/{enrolled['node']['id']}/token", headers=admin)
    assert rotated.status_code == 200
    new_token = rotated.json()['token']
    assert new_token != old_token
    heartbeat = {'cpu_percent':1,'memory_total':1000,'memory_used':100,'disk_total':5000,'disk_used':1000}
    assert client.post('/api/v1/nodes/heartbeat', headers={'X-Node-Token':old_token}, json=heartbeat).status_code == 401
    assert client.post('/api/v1/nodes/heartbeat', headers={'X-Node-Token':new_token}, json=heartbeat).status_code == 200
    assert client.post(f"/api/v1/admin/nodes/{enrolled['node']['id']}/token").status_code == 401


def test_backup_schedule_creation_and_due_dispatch():
    from datetime import datetime, timedelta, timezone
    from app.models import BackupSchedule, GameServer
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'scheduled-backup-node','fqdn':'scheduled.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':1,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':80*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Scheduled SMP','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1
    }).json()
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-scheduled'})
    sid = created['id']
    schedule = client.post(f'/api/v1/admin/servers/{sid}/backup-schedules', headers=admin, json={
        'name':'Nightly world backup','frequency':'daily','retention':5,'enabled':True
    })
    assert schedule.status_code == 201, schedule.text
    assert schedule.json()['retention'] == 5
    with TestingSession() as db:
        row = db.get(BackupSchedule, schedule.json()['id'])
        row.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    queued = client.get('/api/v1/nodes/tasks', headers=node_headers)
    assert queued.status_code == 200
    scheduled = next(task for task in queued.json() if task['action'] == 'backup_create')
    assert scheduled['payload']['label'] == 'scheduled'
    assert scheduled['payload']['retention'] == 5
    assert client.delete(f"/api/v1/admin/servers/{sid}/backup-schedules/{schedule.json()['id']}", headers=admin).status_code == 204


def test_fabric_server_type_and_mod_manager_task_permissions():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'fabric-node','fqdn':'fabric.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':1,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':80*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Fabric SMP','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1,'server_type':'fabric'
    })
    assert created.status_code == 202, created.text
    assert created.json()['server_type'] == 'fabric'
    sid = created.json()['id']
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    assert provision['payload']['server_type'] == 'fabric'
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-fabric'})
    plugin = client.post(f'/api/v1/admin/servers/{sid}/mods', headers=admin, json={'action':'list','kind':'plugin'})
    assert plugin.status_code == 409
    mods = client.post(f'/api/v1/admin/servers/{sid}/mods', headers=admin, json={'action':'list','kind':'mod'})
    assert mods.status_code == 202
    task = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    assert task['action'] == 'mod_manager'
    assert task['payload']['kind'] == 'mod'
    assert client.post(f'/api/v1/admin/servers/{sid}/mods', headers=admin,
        json={'action':'install','kind':'mod','filename':'bad.jar','url':'http://127.0.0.1/evil.jar'}).status_code == 422


def test_additional_server_allocations_queue_container_reconfiguration():
    login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'allocation-node','fqdn':'allocation.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':1,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':80*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Allocation SMP','node_id':enrolled['node']['id'],'memory_mb':1024,'cpu_limit':1
    }).json()
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-allocation'})
    sid = created['id']
    added = client.post(f'/api/v1/admin/servers/{sid}/allocations', headers=admin,
        json={'container_port':25566,'protocol':'udp'})
    assert added.status_code == 202, added.text
    assert added.json()['container_port'] == 25566
    queued = client.get('/api/v1/nodes/tasks', headers=node_headers).json()
    task = next(item for item in queued if item['action'] == 'allocation_update')
    assert task['payload']['allocations'][0]['container_port'] == 25565
    assert task['payload']['allocations'][1]['container_port'] == 25566
    client.post(f"/api/v1/nodes/tasks/{task['id']}/result", headers=node_headers,
        json={'docker_id':'docker-reconfigured','data':{'status':'online','allocations':2}})
    assert client.get(f'/api/v1/admin/servers/{sid}/allocations', headers=admin).json()[0]['protocol'] == 'udp'
    assert client.delete(f"/api/v1/admin/servers/{sid}/allocations/{added.json()['id']}", headers=admin).status_code == 202


def test_personal_api_keys_are_read_only_and_revocable():
    with TestingSession() as db:
        customer = User(email='customer@example.com', username='customer', password_hash=hash_password('Customer-Password-123!'), role='user')
        db.add(customer)
        db.commit()
    admin_login = client.post('/api/v1/auth/login', json={'email':'admin@example.com','password':'Correct-Horse-123!'}).json()
    admin = {'Authorization':f"Bearer {admin_login['access_token']}"}
    customer_login = client.post('/api/v1/auth/login', json={'email':'customer@example.com','password':'Customer-Password-123!'}).json()
    customer_auth = {'Authorization':f"Bearer {customer_login['access_token']}"}
    enrolled = client.post('/api/v1/admin/nodes', headers=admin, json={'name':'api-key-node','fqdn':'api-key.example.test'}).json()
    node_headers = {'X-Node-Token':enrolled['token']}
    client.post('/api/v1/nodes/heartbeat', headers=node_headers, json={
        'cpu_percent':1,'memory_total':8*1024**3,'memory_used':1024**3,'disk_total':80*1024**3,'disk_used':5*1024**3
    })
    created = client.post('/api/v1/admin/servers', headers=admin, json={
        'name':'Customer Server','node_id':enrolled['node']['id'],'owner_email':'customer@example.com','memory_mb':1024,'cpu_limit':1
    }).json()
    provision = client.get('/api/v1/nodes/tasks', headers=node_headers).json()[0]
    client.post(f"/api/v1/nodes/tasks/{provision['id']}/result", headers=node_headers, json={'docker_id':'docker-customer'})
    made = client.post('/api/v1/auth/api-keys', headers=customer_auth, json={'name':'Monitoring','expires_days':30})
    assert made.status_code == 201, made.text
    token = made.json()['api_key']
    key_headers = {'Authorization':f'Bearer {token}'}
    assert token.startswith('lpgp_')
    assert client.get('/api/v1/auth/me', headers=key_headers).json()['username'] == 'customer'
    visible = client.get('/api/v1/admin/servers', headers=key_headers)
    assert visible.status_code == 200
    assert any(server['id'] == created['id'] for server in visible.json())
    denied = client.post(f"/api/v1/admin/servers/{created['id']}/action", headers=key_headers, json={'action':'start'})
    assert denied.status_code == 403
    assert client.get('/api/v1/admin/users', headers=key_headers).status_code == 403
    key_id = made.json()['key']['id']
    assert client.delete(f'/api/v1/auth/api-keys/{key_id}', headers=customer_auth).status_code == 204
    assert client.get('/api/v1/auth/me', headers=key_headers).status_code == 401
