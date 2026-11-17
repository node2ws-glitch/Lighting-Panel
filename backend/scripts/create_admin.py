import argparse
import getpass
from sqlalchemy import select
from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

def main():
    parser = argparse.ArgumentParser(description='Create a Lighting Panel administrator.')
    parser.add_argument('--email', required=True)
    parser.add_argument('--username', required=True)
    args = parser.parse_args()
    password = getpass.getpass('Admin password (12+ characters): ')
    confirm = getpass.getpass('Confirm password: ')
    if len(password) < 12 or password != confirm:
        raise SystemExit('Passwords must match and contain at least 12 characters.')
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        email = args.email.strip().lower()
        if db.scalar(select(User.id).where((User.email == email) | (User.username == args.username))):
            raise SystemExit('That email or username already exists.')
        db.add(User(email=email, username=args.username, password_hash=hash_password(password), role='admin'))
        db.commit()
        print(f'Administrator created: {email}')

if __name__ == '__main__':
    main()
