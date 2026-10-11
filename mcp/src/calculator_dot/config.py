from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_url(value: str, allow_local: bool = False) -> str:
    url = urlsplit(value)
    local = allow_local and url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
    if (
        (url.scheme != "https" and not local)
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("Use a canonical HTTPS URL without credentials, query or fragment")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_public_url: str = "https://calculator-cimd.example.com/mcp"
    django_issuer_url: str = "https://oauth-poc.example.com/"
    django_introspection_url: str = "https://oauth-poc.example.com/mcp-oauth/introspect/"
    introspection_client_id: str = "calculator-mcp-service"
    introspection_client_secret: SecretStr
    mcp_required_scope: str = "calculator:execute"
    allow_local_http: bool = False
    host: str = "127.0.0.1"
    port: int = 8001
    introspection_timeout: float = 5

    @model_validator(mode="after")
    def valid_settings(self):
        for value in (self.mcp_public_url, self.django_issuer_url, self.django_introspection_url):
            validate_url(value, self.allow_local_http)
        self.django_issuer_url = str(AnyHttpUrl(self.django_issuer_url))
        if urlsplit(self.mcp_public_url).path != "/mcp":
            raise ValueError("This PoC serves the canonical /mcp resource")
        if not self.introspection_client_secret.get_secret_value():
            raise ValueError("An introspection service secret is required")
        if not 0 < self.introspection_timeout <= 30:
            raise ValueError("Introspection timeout must be between 0 and 30 seconds")
        return self
