import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import hmac
import jwt
import bcrypt

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-secret-key")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


class LoginRequest(BaseModel):
    password: str


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _check_password(plain: str, stored: str) -> bool:
    """Support bcrypt hashes ($2b$...) and plain-text passwords for migration."""
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        return bcrypt.checkpw(plain.encode(), stored.encode())
    # plain-text fallback — constant-time compare to prevent timing attacks
    return hmac.compare_digest(plain, stored)


from slowapi import Limiter
from slowapi.util import get_remote_address
_limiter = Limiter(key_func=get_remote_address)


@router.post("/login")
@_limiter.limit("10/minute")
def login(request: Request, body: LoginRequest):
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    if not _check_password(body.password, admin_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_token({"role": "admin"})
    return {"access_token": token, "token_type": "bearer"}
