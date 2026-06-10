from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    senha: str = Field(min_length=12, max_length=128)


class RegistrarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    senha: str = Field(min_length=12, max_length=128)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UsuarioResponse(BaseModel):
    id: UUID
    email: str
    papel: str
