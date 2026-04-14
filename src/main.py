from __future__ import annotations

from importlib.metadata import version

from fastapi import FastAPI

app = FastAPI(title="PytStop", version=version("pytstop"))


@app.get("/api/v1/saude")
def saude() -> dict[str, str]:
    return {"status": "ok"}
