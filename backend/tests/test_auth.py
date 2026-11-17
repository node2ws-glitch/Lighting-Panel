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
