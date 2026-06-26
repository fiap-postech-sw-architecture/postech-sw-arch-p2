from __future__ import annotations

import scripts.outbox_dlq as cli


def test_uso_invalido_retorna_2(capsys) -> None:
    assert cli.main(["outbox_dlq.py"]) == 2


def test_requeue_sem_id_retorna_2(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_engine", object)
    assert cli.main(["outbox_dlq.py", "requeue"]) == 2
