from pydantic import BaseModel
from typing import List

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
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
