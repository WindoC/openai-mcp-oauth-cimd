# Django OAuth PoC

A standalone Django 6.0.6 + django-oauth-toolkit 3.4.1 server with built-in users,
login and OAuth consent. It supports one Calculator MCP resource.
Gunicorn runs the Linux container; use Django's runserver for local Windows testing.

Run `uv sync --locked` in this directory, configure the environment as described
in the root README, then run `uv run python manage.py` with `migrate`,
`create_mcp_service`, `createsuperuser` and `runserver`.
The example issuer is `https://oauth-poc.example.com/`. HTTPS mode requires a new
`POC_DJANGO_SECRET_KEY`. SQLite defaults to `django/poc.sqlite3`; the container uses
its dedicated `/data/poc.sqlite3` database.

`MCP_PUBLIC_URL` is the token resource and must match in Django and MCP.
Introspection requires the designated confidential service client, a valid user
token, the correct resource and the `calculator:execute` scope. It does not return
email or profile data. Use a dedicated PoC database.

See [Deployment](../docs/deployment.md).
