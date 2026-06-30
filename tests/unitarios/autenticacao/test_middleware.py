from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.infraestrutura.jwt_service import JWTService
from src.autenticacao.interfaces.middleware import (
    _PERMISSOES,
    exigir_papel,
    obter_usuario_atual,
)

_CHAVE = "test-secret"
_MOCK_SESSION = MagicMock()


class _FakeCredentials:
    def __init__(self, token: str) -> None:
        self.credentials = token


@pytest.fixture(autouse=True)
def _jwt_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _CHAVE)


class TestObterUsuarioAtual:
    def test_sem_credenciais_retorna_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            obter_usuario_atual(credentials=None, session=_MOCK_SESSION)
        assert exc.value.status_code == 401

    def test_token_invalido_retorna_401(self) -> None:
        creds = _FakeCredentials(token="invalido")
        with pytest.raises(HTTPException) as exc:
            obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
        assert exc.value.status_code == 401

    def test_token_expirado_retorna_401(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE, expiracao_minutos=-1)
        token = svc.gerar_access_token(
            usuario_id=uuid4(), email="t@t.com", papel="admin"
        )
        creds = _FakeCredentials(token=token)
        with pytest.raises(HTTPException) as exc:
            obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
        assert exc.value.status_code == 401

    def test_token_valido_retorna_payload(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_access_token(uid, "t@t.com", "admin")
        creds = _FakeCredentials(token=token)
        fake_repo = MagicMock()
        fake_repo.esta_revogado = MagicMock(return_value=False)
        with patch(
            "src.autenticacao.infraestrutura.token_revogado_repository.TokenRevogadoSQLAlchemyRepository",
            return_value=fake_repo,
        ):
            payload = obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
        assert payload["sub"] == str(uid)

    def test_refresh_token_rejeitado_como_access(self) -> None:
        """TD-029: refresh token nao passa no gate de acesso (type != access -> 401).

        Espelha o check `type == refresh` do fluxo de refresh; defense-in-depth
        para qualquer rota futura apenas-autenticada (hoje so o RBAC contem).
        """
        svc = JWTService(chave_secreta=_CHAVE)
        token = svc.gerar_refresh_token(uuid4())
        creds = _FakeCredentials(token=token)
        fake_repo = MagicMock()
        fake_repo.esta_revogado = MagicMock(return_value=False)
        with (
            patch(
                "src.autenticacao.infraestrutura.token_revogado_repository.TokenRevogadoSQLAlchemyRepository",
                return_value=fake_repo,
            ),
            pytest.raises(HTTPException) as exc,
        ):
            obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
        assert exc.value.status_code == 401

    def test_token_revogado_retorna_401(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_access_token(uid, "t@t.com", "admin")
        payload = svc.validar_token(token)
        jti = str(payload["jti"])
        fake_repo = MagicMock()
        fake_repo.esta_revogado = lambda j: j == jti
        with patch(
            "src.autenticacao.infraestrutura.token_revogado_repository.TokenRevogadoSQLAlchemyRepository",
            return_value=fake_repo,
        ):
            creds = _FakeCredentials(token=token)
            with pytest.raises(HTTPException) as exc:
                obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
            assert exc.value.status_code == 401
            assert "revogado" in str(exc.value.detail).lower()


class TestExigirPapel:
    def test_papel_permitido(self) -> None:
        verificar = exigir_papel("admin")
        result = verificar({"papel": "admin", "sub": "123"})  # type: ignore[operator]
        assert result["papel"] == "admin"

    def test_papel_nao_permitido(self) -> None:
        verificar = exigir_papel("admin")
        with pytest.raises(HTTPException) as exc:
            verificar({"papel": "atendente", "sub": "123"})  # type: ignore[operator]
        assert exc.value.status_code == 403

    def test_multiplos_papeis_permitidos(self) -> None:
        verificar = exigir_papel("admin", "mecanico")
        result = verificar({"papel": "mecanico", "sub": "123"})  # type: ignore[operator]
        assert result["papel"] == "mecanico"


class TestHierarquiaDePapeis:
    @pytest.mark.parametrize(
        ("papel_usuario", "papel_exigido"),
        [
            pytest.param("admin", "admin", id="admin-acessa-admin"),
            pytest.param("admin", "atendente", id="admin-acessa-atendente"),
            pytest.param("admin", "mecanico", id="admin-acessa-mecanico"),
            pytest.param("atendente", "atendente", id="atendente-acessa-atendente"),
            pytest.param("mecanico", "mecanico", id="mecanico-acessa-mecanico"),
        ],
    )
    def test_papel_aceito(self, papel_usuario: str, papel_exigido: str) -> None:
        verificar = exigir_papel(papel_exigido)
        result = verificar({"papel": papel_usuario, "sub": "u1"})  # type: ignore[operator]
        assert result["papel"] == papel_usuario

    @pytest.mark.parametrize(
        ("papel_usuario", "papel_exigido"),
        [
            pytest.param("atendente", "admin", id="atendente-nega-admin"),
            pytest.param("atendente", "mecanico", id="atendente-nega-mecanico"),
            pytest.param("mecanico", "admin", id="mecanico-nega-admin"),
            pytest.param("mecanico", "atendente", id="mecanico-nega-atendente"),
        ],
    )
    def test_papel_nao_herda_para_cima_ou_lateral(
        self, papel_usuario: str, papel_exigido: str
    ) -> None:
        verificar = exigir_papel(papel_exigido)
        with pytest.raises(HTTPException) as exc:
            verificar({"papel": papel_usuario, "sub": "u1"})  # type: ignore[operator]
        assert exc.value.status_code == 403


class TestEdgeCasesExigirPapel:
    @pytest.mark.parametrize(
        "papel_valor",
        [
            pytest.param("desconhecido", id="papel-desconhecido"),
            pytest.param("", id="papel-string-vazia"),
            pytest.param("ADMIN", id="papel-case-incorreto"),
        ],
    )
    def test_papel_string_fora_do_enum_retorna_403(self, papel_valor: str) -> None:
        verificar = exigir_papel("admin")
        with pytest.raises(HTTPException) as exc:
            verificar({"papel": papel_valor, "sub": "u1"})  # type: ignore[operator]
        assert exc.value.status_code == 403

    @pytest.mark.parametrize(
        "papel_valor",
        [
            pytest.param(None, id="papel-none"),
            pytest.param(42, id="papel-int"),
            pytest.param(["admin"], id="papel-list"),
            pytest.param({"nome": "admin"}, id="papel-dict"),
        ],
    )
    def test_papel_tipo_nao_string_retorna_403(self, papel_valor: object) -> None:
        verificar = exigir_papel("admin")
        with pytest.raises(HTTPException) as exc:
            verificar({"papel": papel_valor, "sub": "u1"})  # type: ignore[operator]
        assert exc.value.status_code == 403

    def test_payload_sem_papel_retorna_403(self) -> None:
        verificar = exigir_papel("admin")
        with pytest.raises(HTTPException) as exc:
            verificar({"sub": "u1"})  # type: ignore[operator]
        assert exc.value.status_code == 403

    def test_exigir_papel_sem_argumentos_levanta_value_error(self) -> None:
        with pytest.raises(ValueError, match="requer ao menos um papel"):
            exigir_papel()

    def test_exigir_papel_com_valor_fora_do_enum_levanta_value_error(self) -> None:
        with pytest.raises(ValueError, match="papel invalido"):
            exigir_papel("admin", "desconhecido")


class TestGuardasDePermissoes:
    def test_permissoes_cobrem_todos_os_papeis_do_enum(self) -> None:
        assert set(_PERMISSOES.keys()) == set(Papel)

    def test_permissoes_e_mapping_imutavel(self) -> None:
        assert isinstance(_PERMISSOES, Mapping)
        assert isinstance(_PERMISSOES, MappingProxyType)

    def test_valores_de_permissoes_sao_frozenset(self) -> None:
        for papel, permitidos in _PERMISSOES.items():
            assert isinstance(permitidos, frozenset), (
                f"{papel} tem permitidos mutavel: {type(permitidos).__name__}"
            )

    def test_permissoes_nao_podem_ser_mutadas_em_runtime(self) -> None:
        with pytest.raises(TypeError):
            _PERMISSOES[Papel.ATENDENTE] = frozenset({Papel.ADMIN})  # type: ignore[index]
        with pytest.raises(AttributeError):
            _PERMISSOES[Papel.ATENDENTE].add(Papel.ADMIN)  # type: ignore[attr-defined]


class TestEnvLimpeza:
    def test_jwt_secret_nao_vaza_entre_testes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="JWT_SECRET nao configurado"):
            obter_usuario_atual(
                credentials=_FakeCredentials(token="qualquer"),
                session=_MOCK_SESSION,
            )
