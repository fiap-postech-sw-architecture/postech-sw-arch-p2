from __future__ import annotations

from src.autenticacao.infraestrutura.mapping import (
    tokens_revogados_table,
    usuarios_table,
)


class TestMappingAuth:
    def test_usuarios_nome_tabela(self) -> None:
        assert usuarios_table.name == "usuarios"

    def test_usuarios_colunas(self) -> None:
        colunas = {c.name for c in usuarios_table.columns}
        assert colunas == {"id", "email", "senha_hash", "papel"}

    def test_usuarios_id_primary_key(self) -> None:
        assert usuarios_table.c.id.primary_key

    def test_email_unique(self) -> None:
        assert usuarios_table.c.email.unique

    def test_papel_sem_default_admin(self) -> None:
        # Regressao do #96: a coluna papel NAO pode ter default (nem de coluna
        # nem server_default) -- um default "admin" contradiz o fail-safe do
        # #84 (seria fail-OPEN). O papel e sempre setado pelo before_insert a
        # partir do dominio; sem papel, a insercao viola NOT NULL (fail-closed).
        assert usuarios_table.c.papel.default is None
        assert usuarios_table.c.papel.server_default is None
        assert not usuarios_table.c.papel.nullable

    def test_tokens_nome_tabela(self) -> None:
        assert tokens_revogados_table.name == "tokens_revogados"

    def test_tokens_colunas(self) -> None:
        colunas = {c.name for c in tokens_revogados_table.columns}
        assert colunas == {"id", "jti", "revogado_em"}

    def test_tokens_id_primary_key(self) -> None:
        assert tokens_revogados_table.c.id.primary_key

    def test_jti_unique(self) -> None:
        assert tokens_revogados_table.c.jti.unique
