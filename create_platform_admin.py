"""
create_platform_admin.py
Creates the first platform admin account directly in the DB.

Usage:
    .\.venv312\Scripts\python.exe create_platform_admin.py
"""

import utf8_console  # noqa: F401
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

ADMIN_EMAIL    = "admin@bsmart.local"
ADMIN_PASSWORD = "BsmartAdmin2024!"
ADMIN_NAME     = "Platform Admin"

from api.database import engine, SessionLocal
from api.domain_models import Base, User
from api.security import hash_password
from sqlalchemy import select

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    existing = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if existing:
        if not existing.is_platform_admin:
            existing.is_platform_admin = True
            db.commit()
            print(f"✓ Promoted existing user to platform admin: {ADMIN_EMAIL}")
        else:
            print(f"✓ Platform admin already exists: {ADMIN_EMAIL}")
    else:
        user = User(
            email=ADMIN_EMAIL,
            display_name=ADMIN_NAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            is_platform_admin=True,
            active=True,
        )
        db.add(user)
        db.commit()
        print(f"✓ Platform admin created: {ADMIN_EMAIL}")

print(f"\nLogin credentials:")
print(f"  Email   : {ADMIN_EMAIL}")
print(f"  Password: {ADMIN_PASSWORD}")
print(f"\nAdmin panel: http://localhost:5173/#/admin")
