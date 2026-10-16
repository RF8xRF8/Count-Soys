import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.core.security import hash_password
from backend.app.database import Base, SessionLocal, engine
from backend.app.models import User

Base.metadata.create_all(engine)
db = SessionLocal()
try:
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin", daily_quota=100000))
        db.commit()
        print("created admin / admin123")
    else:
        print("admin already exists")
finally:
    db.close()
