from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.autenticacao.dominio.papel import Papel


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    senha: str = Field(min_length=12, max_length=128)


class RegistrarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    senha: str = Field(min_length=12, max_length=128)
    # `papel` e obrigatorio (issue #84): o endpoint e admin-gated, entao quem
    # registra escolhe explicitamente o papel. Omitir -> 422 (nunca um ADMIN
    # silencioso). Pydantic valida contra o enum Papel (StrEnum) — os valores
    # aceitos no JSON sao os do enum em minusculo: "admin"/"mecanico"/"atendente".
    papel: Papel


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
