from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str

class UserSchema(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
