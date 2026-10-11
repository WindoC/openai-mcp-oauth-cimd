import os

# Only the standalone PoC config package is installed by the integration project.
os.environ["POC_LOCAL"] = "true"
os.environ["POC_DJANGO_SECRET_KEY"] = "test-only-not-a-deployment-secret"
os.environ["DJANGO_ISSUER_URL"] = "https://oauth-poc.example.com/"
os.environ["POC_ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
os.environ["MCP_PUBLIC_URL"] = "https://calculator-cimd.example.com/mcp"
os.environ["INTROSPECTION_CLIENT_ID"] = "calculator-mcp-service"

from config.settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
