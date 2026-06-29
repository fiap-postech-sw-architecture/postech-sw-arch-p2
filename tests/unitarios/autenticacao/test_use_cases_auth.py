from __future__ import annotations

from uuid import UUID

import pytest

from src.autenticacao.aplicacao.dtos import LoginDTO, RegistrarDTO
from src.autenticacao.aplicacao.use_cases import Login, Logout, RefreshToken, Registrar
from src.autenticacao.dominio.exceptions import (
    CredenciaisInvalidasException,
    EmailDuplicadoException,
    TokenInvalidoException,
    TokenRevogadoException,
)
from src.autenticacao.dominio.papel import Papel
from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.jwt_service import JWTService
from src.autenticacao.infraestrutura.password_hasher import PasswordHasher, hash_senha


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeUsuarioRepository:
    def __init__(self) -> None:
        self._usuarios: dict[UUID, Usuario] = {}

    def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        return self._usuarios.get(usuario_id)

    def obter_por_email(self, email: str) -> Usuario | None:
        for u in self._usuarios.values():
            if u.email == email:
                return u
        return None

    def salvar(self, usuario: Usuario) -> None:
        self._usuarios[usuario.id] = usuario

    def email_existe(self, email: str) -> bool:
        return any(u.email == email for u in self._usuarios.values())


class FakeTokenRevogadoRepository:
    def __init__(self) -> None:
        self._revogados: set[str] = set()

    def revogar(self, jti: str) -> None:
        self._revogados.add(jti)

    def esta_revogado(self, jti: str) -> bool:
        return jti in self._revogados


class FakePasswordHasher:
    """Spy de `PasswordHasherPort` para provar que o use case usa o port injetado."""

    def __init__(self) -> None:
        self.hashed: list[str] = []

    def hash_senha(self, senha: str) -> str:
        self.hashed.append(senha)
        return f"hashed::{senha}"

    def verificar_senha(self, senha_plana: str, senha_hash: str) -> bool:
        return senha_hash == f"hashed::{senha_plana}"


class FakeJWTService:
    """Spy de `JWTServicePort` para provar que o use case usa o port injetado."""

    def __init__(self) -> None:
        self.access_calls = 0
        self.refresh_calls = 0

    def gerar_access_token(self, usuario_id: UUID, email: str, papel: str) -> str:
        self.access_calls += 1
        return "fake-access"

    def gerar_refresh_token(self, usuario_id: UUID) -> str:
        self.refresh_calls += 1
        return "fake-refresh"

    def validar_token(self, token: str) -> dict[str, object]:
        return {}


class TestRegistrar:
    def test_sucesso(self) -> None:
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        uc = Registrar(repo=repo, uow=uow, password_hasher=PasswordHasher())
        dto = RegistrarDTO(
            email="test@test.com", senha="senhaforte1234", papel=Papel.ADMIN
        )
        result = uc.executar(dto)
        assert result.email == "test@test.com"
        assert result.papel == "admin"

    @pytest.mark.parametrize("papel", [Papel.ADMIN, Papel.MECANICO, Papel.ATENDENTE])
    def test_persiste_papel_informado(self, papel: Papel) -> None:
        # Regressao do bug #84: o papel informado no DTO deve ser o papel
        # persistido — NAO o antigo default ADMIN da factory.
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        uc = Registrar(repo=repo, uow=uow, password_hasher=PasswordHasher())
        dto = RegistrarDTO(
            email=f"{papel.value}@test.com", senha="senhaforte1234", papel=papel
        )
        result = uc.executar(dto)
        assert result.papel == papel.value
        persistido = repo.obter_por_email(f"{papel.value}@test.com")
        assert persistido is not None
        assert persistido.papel is papel

    def test_registrar_mecanico_nao_vira_admin(self) -> None:
        # Guarda nuclear do #84: criar um MECANICO nao pode resultar em ADMIN.
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        uc = Registrar(repo=repo, uow=uow, password_hasher=PasswordHasher())
        uc.executar(
            RegistrarDTO(
                email="mec@test.com", senha="senhaforte1234", papel=Papel.MECANICO
            )
        )
        persistido = repo.obter_por_email("mec@test.com")
        assert persistido is not None
        assert persistido.papel is Papel.MECANICO
        assert persistido.papel is not Papel.ADMIN

    def test_email_duplicado(self) -> None:
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        uc = Registrar(repo=repo, uow=uow, password_hasher=PasswordHasher())
        dto = RegistrarDTO(
            email="test@test.com", senha="senhaforte1234", papel=Papel.ATENDENTE
        )
        uc.executar(dto)
        with pytest.raises(EmailDuplicadoException):
            uc.executar(dto)

    def test_usa_o_password_hasher_injetado(self) -> None:
        # Prova a inversao de dependencia (TD-019): o use case delega ao port
        # injetado, sem importar a infraestrutura de hashing.
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        hasher = FakePasswordHasher()
        uc = Registrar(repo=repo, uow=uow, password_hasher=hasher)
        uc.executar(
            RegistrarDTO(email="a@b.com", senha="senhaforte1234", papel=Papel.ADMIN)
        )
        assert hasher.hashed == ["senhaforte1234"]
        usuario = repo.obter_por_email("a@b.com")
        assert usuario is not None
        assert usuario.senha_hash == "hashed::senhaforte1234"


class TestLogin:
    def test_sucesso(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc, password_hasher=PasswordHasher())
        dto = LoginDTO(email="test@test.com", senha="senhaforte1234")
        result = uc.executar(dto)
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"

    def test_retorna_access_e_refresh(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc, password_hasher=PasswordHasher())
        dto = LoginDTO(email="test@test.com", senha="senhaforte1234")
        result = uc.executar(dto)
        access_payload = jwt_svc.validar_token(result.access_token)
        refresh_payload = jwt_svc.validar_token(result.refresh_token)
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"

    def test_email_nao_encontrado(self) -> None:
        repo = FakeUsuarioRepository()
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc, password_hasher=PasswordHasher())
        with pytest.raises(CredenciaisInvalidasException):
            uc.executar(LoginDTO(email="x@x.com", senha="senhaerrada12"))

    def test_senha_incorreta(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc, password_hasher=PasswordHasher())
        with pytest.raises(CredenciaisInvalidasException):
            uc.executar(LoginDTO(email="test@test.com", senha="erradaerrada1"))

    def test_usa_os_ports_injetados(self) -> None:
        # Prova a inversao (TD-019): o Login delega a verificacao ao
        # PasswordHasherPort e a emissao de tokens ao JWTServicePort injetados,
        # sem acoplar a infraestrutura. Com hasher real o senha_hash "hashed::.."
        # nem validaria; com JWT real os tokens nao seriam "fake-*".
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="a@b.com",
            senha_hash="hashed::senhaforte1234",
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        hasher = FakePasswordHasher()
        jwt = FakeJWTService()
        uc = Login(repo=repo, jwt_service=jwt, password_hasher=hasher)
        result = uc.executar(LoginDTO(email="a@b.com", senha="senhaforte1234"))
        assert result.access_token == "fake-access"
        assert result.refresh_token == "fake-refresh"
        assert jwt.access_calls == 1
        assert jwt.refresh_calls == 1


class TestLogout:
    def test_revoga_jti_do_token(self) -> None:
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        from uuid import uuid4

        token = jwt_svc.gerar_access_token(uuid4(), "t@t.com", "admin")
        uc = Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow)
        result = uc.executar(token)
        assert "mensagem" in result
        payload = jwt_svc.validar_token(token)
        assert token_repo.esta_revogado(str(payload["jti"]))

    def test_retorna_confirmacao(self) -> None:
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        from uuid import uuid4

        token = jwt_svc.gerar_access_token(uuid4(), "t@t.com", "admin")
        uc = Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow)
        result = uc.executar(token)
        assert result["mensagem"] == "Logout realizado com sucesso"


class TestRefreshToken:
    def test_rotacao_sucesso(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        refresh = jwt_svc.gerar_refresh_token(usuario.id)
        old_payload = jwt_svc.validar_token(refresh)
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        result = uc.executar(refresh)
        assert result.access_token
        assert result.refresh_token
        assert token_repo.esta_revogado(str(old_payload["jti"]))

    def test_rejeita_access_token_como_refresh(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        access = jwt_svc.gerar_access_token(usuario.id, "test@test.com", "admin")
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        with pytest.raises(TokenInvalidoException, match="Token nao e do tipo refresh"):
            uc.executar(access)

    def test_rejeita_token_ja_revogado(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        refresh = jwt_svc.gerar_refresh_token(usuario.id)
        payload = jwt_svc.validar_token(refresh)
        token_repo.revogar(str(payload["jti"]))
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        with pytest.raises(TokenRevogadoException):
            uc.executar(refresh)

    def test_usuario_inexistente(self) -> None:
        repo = FakeUsuarioRepository()
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        from uuid import uuid4

        refresh = jwt_svc.gerar_refresh_token(uuid4())
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        with pytest.raises(
            CredenciaisInvalidasException, match="Usuario nao encontrado"
        ):
            uc.executar(refresh)
