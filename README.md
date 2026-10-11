# openai-mcp-oauth-cimd

A standalone Django OAuth server and Calculator MCP proof of concept for ChatGPT.
This PoC supports **one Calculator MCP** and contains two independent services:

- `django/`: Django 6.0.6 + django-oauth-toolkit 3.4.1, with built-in username/password login.
- `mcp/`: a stateless FastMCP Calculator resource server, without an OAuth proxy or persistent volume.
- Repository root: integration tests and documentation.

Django owns its users, OAuth clients and SQLite database at `django/poc.sqlite3`.
`/accounts/login/` is a local route within this Django service.
The domains below are examples; replace them with your HTTPS deployment hosts.

| Purpose | Example URL |
| --- | --- |
| OAuth base / issuer | `https://oauth-poc.example.com/` |
| AS metadata | `https://oauth-poc.example.com/.well-known/oauth-authorization-server` |
| Authorization / token | `https://oauth-poc.example.com/o/authorize/`, `/o/token/` |
| Introspection | `https://oauth-poc.example.com/mcp-oauth/introspect/` |
| MCP resource | `https://calculator-cimd.example.com/mcp` |

The issuer is the root URL, including its trailing slash, and must match in both services.
CIMD is enabled and restricted to chatgpt.com; DCR is disabled. DOT 3.4.1 supports
public CIMD clients, so the adapter negotiates `none` only when explicitly offered
by the client metadata. S256 PKCE is required. User accounts are provisioned locally.

## Local setup

In the first PowerShell terminal, starting from your checkout:

```powershell
cd django
uv sync --locked
$env:POC_LOCAL='true'
$env:POC_ALLOWED_HOSTS='localhost,127.0.0.1,oauth-poc.example.com'
$env:DJANGO_ISSUER_URL='https://oauth-poc.example.com/'
$env:MCP_PUBLIC_URL='https://calculator-cimd.example.com/mcp'
$env:INTROSPECTION_CLIENT_SECRET=uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
uv run python manage.py migrate
uv run python manage.py create_mcp_service
uv run python manage.py createsuperuser
uv run python manage.py runserver 127.0.0.1:8000
```

In a second terminal, starting from your checkout, set the same service secret
through a secure channel and start MCP. Do not commit the secret.

```powershell
cd mcp
uv sync --locked
$env:DJANGO_ISSUER_URL='https://oauth-poc.example.com/'
$env:DJANGO_INTROSPECTION_URL='https://oauth-poc.example.com/mcp-oauth/introspect/'
$env:MCP_PUBLIC_URL='https://calculator-cimd.example.com/mcp'
$env:ALLOW_LOCAL_HTTP='true'
# Set INTROSPECTION_CLIENT_SECRET to the same value used by create_mcp_service.
uv run calculator-mcp
```

Django reads environment variables; `django/.env.example` is a reference and is
not loaded automatically. MCP can load `mcp/.env` from its working directory.
Local HTTP is for loopback testing. Configure HTTPS routing for the example public
URLs above, or adjust both services consistently for your local setup.
`create_mcp_service` refuses to overwrite an existing client. If the resource URL
changes, update the settings and client in the dedicated PoC database.

## Verification and deployment

```powershell
# Run from the repository root.
uv sync --locked
uv sync --project django --locked
uv sync --project mcp --locked
uv run python -m pytest
uv run ruff check django/config django/poc_oauth django/manage.py mcp/src mcp/tests tests
cd mcp
uv run python -m pytest
```

[Deployment](docs/deployment.md) · [Architecture](docs/architecture.md) ·
[ChatGPT acceptance](docs/chatgpt-oauth-setup.md) · [Test report](docs/test-report.md)

A real ChatGPT connection and Calculator call have succeeded. Container and
Kubernetes deployment remain unverified. Runtime secrets, databases and generated
files are excluded by `.gitignore`; publish the Git checkout, not the entire working folder.
