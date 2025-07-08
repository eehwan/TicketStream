from typing import Optional
from pydantic import BaseModel

# ===============================
# User Schemas
# ===============================

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    password: Optional[str] = None
    is_active: Optional[bool] = None

class User(UserBase):
    id: int
    is_active: Optional[bool] = True

    class Config:
        from_attributes = True

# ===============================
# Token Schema
# ===============================

class Token(BaseModel):
    access_token: str
    token_type: str