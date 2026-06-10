"""CLI: ``python -m full_test <subcomando>``.

**Requisito de execucao:** o pacote ``full_test`` nao e instalado via
setuptools (o `pyproject` empacota apenas `src*`), entao rodar este modulo
diretamente exige `PYTHONPATH=full-test` a partir da raiz do repo. O
Makefile (`FULL_TEST_PY`) ja cuida disso. Exemplo manual:

    PYTHONPATH=full-test uv run python -m full_test healthwait

Subcomandos:
  - healthwait           — espera a API responder
  - seed                 — roda seed_completo (resetando DB)
  - reset                — so reseta o DB (sem seed)
  - run --plano=full|ci  — executa o plano via pytest

Implementacao deliberadamente enxuta (argparse) pra nao adicionar dep extra.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _cmd_healthwait(args: argparse.Namespace) -> int:
    from full_test.seeders.config import carregar_config
    from full_test.support.health import wait_for_saude

    config = carregar_config()
    try:
        wait_for_saude(base_url=config.base_url, timeout_s=args.timeout)
        print(f"OK: {config.base_url}/api/v1/saude respondeu 200")
        return 0
    except TimeoutError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


def _cmd_seed(args: argparse.Namespace) -> int:
    from full_test.seeders.orquestrar import seed_completo

    resultado = seed_completo(resetar=args.reset)
    resumo = {
        "usuarios_inseridos": resultado["usuarios_inseridos"],
        "servicos": len(resultado["servicos"]),  # type: ignore[arg-type]
        "itens_estoque": len(resultado["itens_estoque"]),  # type: ignore[arg-type]
    }
    print(json.dumps(resumo))
    return 0


def _cmd_reset(args: argparse.Namespace) -> int:
    from full_test.seeders.config import carregar_config
    from full_test.seeders.reset import resetar

    config = carregar_config()
    resetar(config.database_url)
    print("DB resetado (TRUNCATE CASCADE).")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    teste = (
        "full-test/tests/test_parallel_usage.py::test_plano_full"
        if args.plano == "full"
        else "full-test/tests/test_parallel_usage.py::test_plano_ci"
    )
    cmd = ["uv", "run", "pytest", teste, "-v"]
    # S603: cmd e lista hardcoded, argumentos limitados a choices do argparse.
    return subprocess.call(cmd)  # noqa: S603


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="full_test", description="Harness E2E concorrente"
    )
    subs = parser.add_subparsers(dest="subcomando", required=True)

    hw = subs.add_parser("healthwait", help="aguarda /api/v1/saude responder")
    hw.add_argument("--timeout", type=float, default=60.0)
    hw.set_defaults(func=_cmd_healthwait)

    sd = subs.add_parser("seed", help="roda seed_completo")
    sd.add_argument("--no-reset", dest="reset", action="store_false", default=True)
    sd.set_defaults(func=_cmd_seed)

    rs = subs.add_parser("reset", help="TRUNCATE CASCADE das tabelas do app")
    rs.set_defaults(func=_cmd_reset)

    rn = subs.add_parser("run", help="executa o plano via pytest")
    rn.add_argument("--plano", choices=("full", "ci"), default="full")
    rn.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
