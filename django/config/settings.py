"""Standalone Django OAuth PoC settings with a dedicated SQLite database."""

import os
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent
POC_LOCAL = os.getenv("POC_LOCAL", "false").lower() == "true"
DEBUG = POC_LOCAL
SECRET_KEY = os.getenv("POC_DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not POC_LOCAL:
        raise RuntimeError("Set POC_DJANGO_SECRET_KEY for HTTPS deployment")
    SECRET_KEY = "local-only-poc-key"

MCP_ISSUER = os.getenv("DJANGO_ISSUER_URL", "https://oauth-poc.example.com/")
MCP_RESOURCE_URI = os.getenv("MCP_PUBLIC_URL", "https://calculator-cimd.example.com/mcp")
MCP_INTROSPECTION_CLIENT_ID = os.getenv("INTROSPECTION_CLIENT_ID", "calculator-mcp-service")
# Optional trusted SNI relay for the fixed ChatGPT metadata URL only.
CIMD_CHATGPT_SNI_PROXY_IP = os.getenv("CIMD_CHATGPT_SNI_PROXY_IP", "")
resource = urlsplit(MCP_RESOURCE_URI)
local_resource = (
    POC_LOCAL and resource.scheme == "http" and resource.hostname in {"localhost", "127.0.0.1"}
)
if (
    (resource.scheme != "https" and not local_resource)
    or not resource.hostname
    or resource.username
    or resource.password
    or resource.query
    or resource.fragment
):
    raise RuntimeError("Use a canonical HTTPS MCP resource (loopback HTTP only in local mode)")
issuer = urlsplit(MCP_ISSUER)
if issuer.scheme != "https" and not (
    POC_LOCAL and issuer.scheme == "http" and issuer.hostname in {"localhost", "127.0.0.1"}
):
    raise RuntimeError("Use an HTTPS issuer (loopback HTTP requires POC_LOCAL=true)")
if not issuer.hostname or issuer.username or issuer.password or issuer.query or issuer.fragment:
    raise RuntimeError("Use a canonical issuer without credentials/query/fragment")

ALLOWED_HOSTS = os.getenv("POC_ALLOWED_HOSTS", "oauth-poc.example.com").split(",")
CSRF_TRUSTED_ORIGINS = [f"{issuer.scheme}://{issuer.netloc}"]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "oauth2_provider",
    "poc_oauth",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("POC_DB_PATH", str(BASE_DIR / "poc.sqlite3")),
    }
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
SESSION_COOKIE_SECURE = not POC_LOCAL
CSRF_COOKIE_SECURE = not POC_LOCAL
SECURE_SSL_REDIRECT = not POC_LOCAL
# Deployment ingress must strip untrusted forwarded headers.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
OAUTH2_PROVIDER = {
    "OIDC_ENABLED": False,
    "OIDC_ISS_ENDPOINT": MCP_ISSUER,
    "SCOPES": {"calculator:execute": "Use Calculator"},
    "DEFAULT_SCOPES": [],
    "CIMD_ENABLED": True,
    "CIMD_ALLOWED_HOSTS": ["chatgpt.com"],
    "CIMD_REGISTRATION_PERMISSION_CLASSES": ["oauth2_provider.cimd.HostAllowlistCIMDPermission"],
    "CIMD_METADATA_FETCHER": "poc_oauth.cimd.ChatGPTMetadataFetcher",
    "DCR_ENABLED": False,
    "PKCE_REQUIRED": True,
    "OAUTH2_RESPONSE_TYPES_SUPPORTED": ["code"],
    "OAUTH2_GRANT_TYPES_SUPPORTED": ["authorization_code", "refresh_token"],
    "OAUTH2_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED": [
        "none",
        "client_secret_basic",
        "client_secret_post",
    ],
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
    "ROTATE_REFRESH_TOKEN": True,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "REFRESH_TOKEN_GRACE_PERIOD_SECONDS": 0,
    "REFRESH_TOKEN_EXPIRE_SECONDS": 86400,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 600,
}

# DOT reports CIMD fetch/validation failures at INFO; surface them in container logs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "poc_oauth.introspection": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "oauth2_provider.cimd": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
