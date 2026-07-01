import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.database import get_conn

SECRET_KEY = "fschp-nenep-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def authenticate_user(username: str, password: str):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
    ).fetchone()
    conn.close()
    if not user:
        return None
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return None
    return dict(user)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
    ).fetchone()
    conn.close()

    if user is None:
        raise credentials_exception
    return {
        "username": username,
        "role": role,
        "display_name": user["display_name"],
        "folder": user["folder"]
    }

def check_role(allowed_roles: list):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập"
            )
        return current_user
    return role_checker