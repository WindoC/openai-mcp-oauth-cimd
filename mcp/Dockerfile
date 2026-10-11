FROM ghcr.io/astral-sh/uv:0.10.1 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev && groupadd -g 10001 mcp && useradd -u 10001 -g mcp mcp
ENV HOST=0.0.0.0 PORT=8001
USER 10001:10001
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=3s CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=2)"]
CMD ["/app/.venv/bin/python", "-m", "calculator_dot.server"]
