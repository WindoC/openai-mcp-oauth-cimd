FROM ghcr.io/astral-sh/uv:0.10.1 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY config ./config
COPY poc_oauth ./poc_oauth
COPY templates ./templates
COPY manage.py ./
RUN uv sync --locked --no-dev && groupadd -g 10001 oauth && useradd -u 10001 -g oauth oauth && mkdir /data && chown 10001:10001 /data
RUN POC_LOCAL=true /app/.venv/bin/python manage.py collectstatic --noinput
USER 10001:10001
EXPOSE 8000
CMD ["/app/.venv/bin/gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--access-logfile", "-"]
