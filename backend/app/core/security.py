from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from ..config import settings

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: int, username: str, role: str, token_type: str, expires_delta: timedelta) -> str:
    # JWT 的 iat/exp 是绝对时间戳，按规范必须用 UTC，这里不要改成北京时间。
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "username": username, "role": role, "type": token_type, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise JWTError("invalid token type")
    return payload
