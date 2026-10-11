import time

import httpx
import pytest

from calculator_dot.auth import DjangoTokenVerifier
from calculator_dot.config import Settings


def test_default_urls_use_standalone_oauth():
    config = Settings(_env_file=None, introspection_client_secret="test-only-secret")
    assert config.django_issuer_url == "https://oauth-poc.example.com/"
    assert config.django_introspection_url == "https://oauth-poc.example.com/mcp-oauth/introspect/"


@pytest.mark.parametrize("scope", ["calculator:execute", "other:execute"])
async def test_scope_is_enforced_in_mcp_environment(scope):
    config = Settings(_env_file=None, introspection_client_secret="test-only-secret")
    claims = {
        "active": True,
        "sub": "1",
        "client_id": "chatgpt",
        "iss": config.django_issuer_url,
        "aud": [config.mcp_public_url],
        "scope": scope,
        "exp": int(time.time()) + 600,
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=claims),
        )
    ) as client:
        token = await DjangoTokenVerifier(config, client).verify_token("test-token")
        assert (token is not None) == (scope == "calculator:execute")
