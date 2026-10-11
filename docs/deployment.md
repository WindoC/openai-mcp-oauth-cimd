# Standalone deployment

| Service | Public URL | Build context |
| --- | --- | --- |
| Django OAuth | https://oauth-poc.example.com/ | django/ |
| Calculator MCP | https://calculator-cimd.example.com/mcp | mcp/ |

Each project has its own pyproject.toml, uv.lock and Python 3.12 environment.
The root project's environment is only for cross-service tests.

Build from the repository root:

```powershell
docker build -t oauth-poc:0.1.0 ./django
docker build -t calculator-cimd:0.1.0 ./mcp
```

Supply a new POC_DJANGO_SECRET_KEY and INTROSPECTION_CLIENT_SECRET via environment
or secret manager. The latter must be at least 32 random characters; never reuse
production credentials. Configure DNS/TLS for the two public hosts.

The root docker-compose.yml binds ports 8000/8001 to loopback for an HTTPS reverse
proxy. It uses a new named SQLite volume and runs Django migration before Gunicorn.
For first setup, build, start Django, provision its service client and test account,
then start MCP. Supply the same service secret when provisioning and to MCP:

```powershell
docker compose build
docker compose up -d django
docker compose exec -e INTROSPECTION_CLIENT_SECRET django /app/.venv/bin/python manage.py create_mcp_service
docker compose exec django /app/.venv/bin/python manage.py createsuperuser
docker compose up -d mcp
```

The exec -e option passes the existing shell environment variable into provisioning;
the secret is not permanently exposed to the Django web process by the compose file.
The command refuses an existing client, preventing accidental credential overwrite.

For Kubernetes, django/deploy/oauth.yaml is a single-replica Recreate deployment
with a dedicated SQLite PVC, Service and oauth-poc.example.com TLS Ingress.
mcp/deploy/mcp.yaml remains a stateless MCP deployment. Replace image registry,
storage class, ingress class and TLS settings. Create oauth-poc Secret with
django-secret-key, and calculator-cimd Secret with introspection-client-secret
outside Git. Provision service/user using the Django runner with its own DB.

Forwarded proto headers must be sanitized by the trusted ingress so Django can
build HTTPS URLs and validate CSRF. Mounting services below a different path is not
covered by this PoC. The issuer is the root URL, including its canonical trailing slash.
Django serves collected static admin assets directly for this PoC.

Container builds and Kubernetes deployment have not been verified. Public ChatGPT
authorization and a Calculator call have succeeded. Use a dedicated PoC database
for POC_DB_PATH.
