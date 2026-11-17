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
