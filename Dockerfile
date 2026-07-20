FROM ghcr.io/astral-sh/uv:0.11.29 AS uv

FROM python:3.13-slim-bookworm

COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev
RUN mkdir --parents /data && chown 10001:10001 /data

USER 10001:10001

CMD ["rootspan-api"]
