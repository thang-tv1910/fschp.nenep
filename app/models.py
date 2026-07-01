from pydantic import BaseModel
from typing import Optional, List

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    display_name: str

class UserInfo(BaseModel):
    username: str
    role: str
    display_name: str

class PermissionInfo(BaseModel):
    tabs: List[str]
    folders: List[str]
    can_upload: bool
    can_manage_users: bool