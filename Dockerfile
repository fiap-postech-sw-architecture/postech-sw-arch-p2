FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

RUN groupadd -r pytstop && useradd -r -g pytstop pytstop

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

RUN chmod +x entrypoint.sh

USER pytstop
EXPOSE 8000
CMD ["./entrypoint.sh"]
