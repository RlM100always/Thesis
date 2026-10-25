"""Manual platform-admin bootstrap; explicit environment credentials only.

Required environment values: BSMART_ADMIN_EMAIL and BSMART_ADMIN_PASSWORD.
Never commit an administrator password in a source file.
"""
import os
from sqlalchemy import select
from api.database import SessionLocal, create_schema
from api.domain_models import User
from api.security import hash_password

email = os.environ.get("BSMART_ADMIN_EMAIL", "").strip().lower()
password = os.environ.get("BSMART_ADMIN_PASSWORD", "")
if not email or len(password) < 16:
    raise SystemExit("Set BSMART_ADMIN_EMAIL and a strong BSMART_ADMIN_PASSWORD (16+ chars) in your private environment.")

create_schema()
with SessionLocal() as db:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        raise SystemExit("Account already exists; refusing to elevate/reset a password automatically.")
    db.add(User(email=email, display_name="Platform Administrator", password_hash=hash_password(password),
                active=True, is_platform_admin=True))
    db.commit()
print("Platform admin provisioned. Open /#/login and use the credentials from your environment.")
