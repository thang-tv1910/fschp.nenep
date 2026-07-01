from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import get_settings
from app.database import get_conn
from app.security import verify_password

settings = get_settings()
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def authenticate_user(username: str, password: str):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
    ).fetchone()
    conn.close()
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    return dict(user)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

async def get_current_user(
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    cookie_token: Optional[str] = Cookie(default=None, alias=settings.cookie_name),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = bearer_token or cookie_token
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
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
        "role": user["role"],
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
