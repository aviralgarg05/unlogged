# The Python service. Replay is the default, so this image needs no credentials to be useful.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first, so a source change does not re-resolve them.
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --no-install-project --no-dev

COPY src/ src/
COPY fixtures/ fixtures/
COPY cassettes/ cassettes/
RUN uv sync --no-dev

ENV UNLOGGED_REPLAY=1 PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "unlogged.web:app", "--host", "0.0.0.0", "--port", "8000"]
