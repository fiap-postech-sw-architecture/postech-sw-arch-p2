from __future__ import annotations

from uuid import UUID

import pytest

from src.autenticacao.aplicacao.dtos import LoginDTO, RegistrarDTO
from src.autenticacao.aplicacao.use_cases import (
    _HASH_DUMMY_TIMING,
    Login,
    Logout,
    RefreshToken,
    Registrar,
)
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
from tests.unitarios.fakes import FakeUnitOfWork


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

    def revogar(self, jti: str) -> bool:
        if jti in self._revogados:
            return False
        self._revogados.add(jti)
        return True

    def esta_revogado(self, jti: str) -> bool:
        return jti in self._revogados


class FakePasswordHasher:
    """Spy de `PasswordHasherPort` para provar que o use case usa o port injetado."""

    def __init__(self) -> None:
        self.hashed: list[str] = []
        self.verificados: list[str] = []

    def hash_senha(self, senha: str) -> str:
        self.hashed.append(senha)
        return f"hashed::{senha}"

    def verificar_senha(self, senha_plana: str, senha_hash: str) -> bool:
        self.verificados.append(senha_hash)
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

    def test_email_normalizado_para_lowercase(self) -> None:
        # E-mail e armazenado em caixa baixa; registrar de novo com outra
        # caixa e duplicata (#167).
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        uc = Registrar(repo=repo, uow=uow, password_hasher=PasswordHasher())
        result = uc.executar(
            RegistrarDTO(
                email="User@Test.COM", senha="senhaforte1234", papel=Papel.ADMIN
            )
        )
        assert result.email == "user@test.com"
        assert repo.obter_por_email("user@test.com") is not None
        with pytest.raises(EmailDuplicadoException):
            uc.executar(
                RegistrarDTO(
                    email="uSeR@tEsT.com", senha="senhaforte1234", papel=Papel.ADMIN
                )
            )

    def test_integrity_error_no_commit_vira_email_duplicado(self) -> None:
        # Corrida check-then-insert (#167): email_existe passa nos dois
        # registros concorrentes e o segundo estoura o UNIQUE no flush/commit.
        # O IntegrityError deve virar o mesmo 409 do caminho sequencial.
        from sqlalchemy.exc import IntegrityError

        class RepoQueEstouraUnique(FakeUsuarioRepository):
            def salvar(self, usuario: Usuario) -> None:
                raise IntegrityError(
                    "INSERT", {}, Exception("duplicate key: usuarios.email")
                )

        uow = FakeUnitOfWork()
        uc = Registrar(
            repo=RepoQueEstouraUnique(), uow=uow, password_hasher=PasswordHasher()
        )
        with pytest.raises(EmailDuplicadoException):
            uc.executar(
                RegistrarDTO(
                    email="race@test.com", senha="senhaforte1234", papel=Papel.ADMIN
                )
            )

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

    def test_login_com_email_em_caixa_mista(self) -> None:
        # O login normaliza o e-mail para lowercase antes da busca (#167):
        # quem se registrou como user@test.com entra digitando USER@Test.com.
        repo = FakeUsuarioRepository()
        repo.salvar(
            Usuario.criar(
                email="user@test.com",
                senha_hash=hash_senha("senhaforte1234"),
                papel=Papel.ADMIN,
            )
        )
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc, password_hasher=PasswordHasher())
        result = uc.executar(LoginDTO(email="USER@Test.com", senha="senhaforte1234"))
        assert result.access_token

    def test_email_inexistente_verifica_hash_dummy(self) -> None:
        # CWE-208 (#167): com e-mail desconhecido o use case ainda paga um
        # verify de senha (contra o hash dummy fixo) antes do 401 -- o tempo de
        # resposta nao pode denunciar quais e-mails existem.
        repo = FakeUsuarioRepository()
        hasher = FakePasswordHasher()
        uc = Login(repo=repo, jwt_service=FakeJWTService(), password_hasher=hasher)
        with pytest.raises(CredenciaisInvalidasException):
            uc.executar(LoginDTO(email="naoexiste@x.com", senha="qualquercoisa12"))
        assert hasher.verificados == [_HASH_DUMMY_TIMING]

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

    def test_revoga_refresh_quando_enviado(self) -> None:
        # Issue #118 (CWE-613): com o refresh no corpo, o logout revoga a
        # sessao inteira -- ambos os jti (access e refresh).
        from uuid import uuid4

        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        usuario_id = uuid4()
        access = jwt_svc.gerar_access_token(usuario_id, "t@t.com", "admin")
        refresh = jwt_svc.gerar_refresh_token(usuario_id)
        uc = Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow)

        uc.executar(access, refresh_token=refresh)

        assert token_repo.esta_revogado(str(jwt_svc.validar_token(access)["jti"]))
        assert token_repo.esta_revogado(str(jwt_svc.validar_token(refresh)["jti"]))

    def test_refresh_pos_logout_e_rejeitado(self) -> None:
        # Prova end-to-end de #118: apos o logout com refresh, o fluxo de
        # refresh rejeita o token revogado (antes: cunhava novo par).
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="t@t.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        access = jwt_svc.gerar_access_token(usuario.id, "t@t.com", "admin")
        refresh = jwt_svc.gerar_refresh_token(usuario.id)
        Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow).executar(
            access, refresh_token=refresh
        )
        refresh_uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        with pytest.raises(TokenRevogadoException):
            refresh_uc.executar(refresh)

    def test_logout_com_refresh_token_no_header_e_rejeitado(self) -> None:
        # Simetria com o gate de acesso (TD-029, #167): so um ACCESS token
        # autentica o logout; um refresh valido no header -> 401.
        from uuid import uuid4

        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        refresh = jwt_svc.gerar_refresh_token(uuid4())
        uc = Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow)
        with pytest.raises(TokenInvalidoException, match="Token nao e do tipo access"):
            uc.executar(refresh)
        assert not token_repo.esta_revogado(str(jwt_svc.validar_token(refresh)["jti"]))

    def test_refresh_de_outro_usuario_nao_e_revogado(self) -> None:
        # A revogacao do refresh e best-effort e escopada ao dono: um refresh
        # de OUTRO usuario enviado no corpo nao e revogado (so o access do
        # solicitante).
        from uuid import uuid4

        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        access = jwt_svc.gerar_access_token(uuid4(), "eu@t.com", "admin")
        refresh_alheio = jwt_svc.gerar_refresh_token(uuid4())
        uc = Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow)

        uc.executar(access, refresh_token=refresh_alheio)

        assert not token_repo.esta_revogado(
            str(jwt_svc.validar_token(refresh_alheio)["jti"])
        )


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

    def test_segundo_uso_do_mesmo_refresh_e_rejeitado(self) -> None:
        # Single-use (#167): reusar o refresh apos a rotacao -> 401.
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=FakeTokenRevogadoRepository(),
            usuario_repo=repo,
            uow=FakeUnitOfWork(),
        )
        refresh = jwt_svc.gerar_refresh_token(usuario.id)
        uc.executar(refresh)
        with pytest.raises(TokenRevogadoException):
            uc.executar(refresh)

    def test_corrida_de_uso_simultaneo_do_refresh_e_rejeitada(self) -> None:
        # Corrida do single-use (#167): dois refreshes concorrentes passam
        # ambos no pre-check `esta_revogado` (aqui simulado por um fake que
        # sempre responde False); a atomicidade vem do `revogar` devolver
        # False para o perdedor -- que recebe TokenRevogadoException.
        class RepoComJanelaDeCorrida(FakeTokenRevogadoRepository):
            def esta_revogado(self, jti: str) -> bool:
                return False

        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com",
            senha_hash=hash_senha("senhaforte1234"),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=RepoComJanelaDeCorrida(),
            usuario_repo=repo,
            uow=FakeUnitOfWork(),
        )
        refresh = jwt_svc.gerar_refresh_token(usuario.id)
        uc.executar(refresh)
        with pytest.raises(TokenRevogadoException):
            uc.executar(refresh)
