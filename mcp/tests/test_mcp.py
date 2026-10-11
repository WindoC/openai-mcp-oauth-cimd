import time

import httpx
import pytest

from calculator_dot.auth import DjangoTokenVerifier, IdentityUnavailable
from calculator_dot.config import Settings
from calculator_dot.server import create_app

ISSUER = "https://oauth-poc.example.com/"
RESOURCE = "https://calculator-cimd.example.com/mcp"
SERVICE_SECRET = "local-test-service-secret-32-characters-long"


def config():
    return Settings(
        _env_file=None,
        introspection_client_secret=SERVICE_SECRET,
        mcp_public_url=RESOURCE,
        django_issuer_url=ISSUER,
        django_introspection_url="https://oauth-poc.example.com/mcp-oauth/introspect/",
    )


def good_claims(**changes):
    return {
        "active": True,
        "sub": "123",
        "client_id": "chatgpt",
        "iss": ISSUER,
        "aud": [RESOURCE],
        "scope": "calculator:execute",
        "exp": int(time.time()) + 600,
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"active": False},
        {"active": "true"},
        {"sub": ""},
        {"sub": None},
        {"client_id": None},
        {"aud": None},
        {"aud": [RESOURCE + "/"]},
        {"aud": ["https://other.example/mcp"]},
        {"scope": "profile"},
        {"exp": int(time.time()) - 1},
        {"exp": None},
        {"iss": "wrong"},
    ],
)
async def test_verifier_rejects_bad_claims(changes, caplog):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=good_claims(**changes)),
        )
    ) as client:
        verifier = DjangoTokenVerifier(config(), client)
        assert await verifier.verify_token("test-token") is None
    assert "token_rejected reason=" in caplog.text
    assert "test-token" not in caplog.text
    assert SERVICE_SECRET not in caplog.text


async def test_no_validation_cache():
    calls = []

    def upstream(request):
        calls.append(request)
        assert request.headers["authorization"].startswith("Basic ")
        assert b"token=test-token" in request.content
        return httpx.Response(200, json=good_claims(active=len(calls) == 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        verifier = DjangoTokenVerifier(config(), client)
        assert await verifier.verify_token("test-token")
        assert await verifier.verify_token("test-token") is None
        assert len(calls) == 2


@pytest.mark.parametrize("failure", ["timeout", "server", "malformed", "redirect"])
async def test_identity_outage_is_503(failure):
    def upstream(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private-upstream-data", request=request)
        if failure == "server":
            return httpx.Response(500, text="private-upstream-data")
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://evil.example"})
        return httpx.Response(200, text="private-upstream-data")

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as upstream_client:
        verifier = DjangoTokenVerifier(config(), upstream_client)
        with pytest.raises(IdentityUnavailable):
            await verifier.verify_token("test-token")
        app = create_app(config(), verifier)
        async with (
            app.lifespan(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url=RESOURCE.removesuffix("/mcp"),
            ) as client,
        ):
            response = await client.post("/mcp", headers={"Authorization": "Bearer test-token"})
            assert response.status_code == 503
            assert "private-upstream-data" not in response.text


async def test_metadata_and_unauthenticated_request():
    app = create_app(config())
    async with (
        app.lifespan(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=RESOURCE.removesuffix("/mcp"),
        ) as client,
    ):
        metadata = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()
        assert metadata["resource"] == RESOURCE
        assert metadata["authorization_servers"] == [ISSUER]
        response = await client.post("/mcp")
        assert response.status_code == 401
        assert "/.well-known/oauth-protected-resource/mcp" in response.headers["www-authenticate"]


@pytest.mark.parametrize(
    "url",
    ["http://example.com/mcp", "https://x/mcp?x=1", "https://user:secret@x/mcp", "https://x/other"],
)
def test_unsafe_configuration_rejected(url):
    with pytest.raises(ValueError):
        Settings(_env_file=None, introspection_client_secret=SERVICE_SECRET, mcp_public_url=url)
