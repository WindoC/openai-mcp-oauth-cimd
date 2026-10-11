import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from oauth2_provider.cimd import SafeMetadataFetcher
from oauth2_provider.models import get_application_model

ISSUER = "https://oauth-poc.example.com/"
RESOURCE = "https://calculator-cimd.example.com/mcp"
CLIENT_ID = "https://chatgpt.com/oauth/client.json"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
SERVICE_SECRET = "local-test-service-secret-32-characters-long"
VERIFIER = "a" * 64


@pytest.fixture
def oauth_setup(db, monkeypatch):
    metadata = {
        "client_id": CLIENT_ID,
        "client_name": "ChatGPT",
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "private_key_jwt",
        "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
    }
    monkeypatch.setattr(SafeMetadataFetcher, "fetch", lambda self, client_id: (metadata, 300))
    user = get_user_model().objects.create_user(
        username="poc-user",
        email="poc@example.com",
        password="poc-password-long",
    )
    model = get_application_model()
    service = model.objects.create(
        client_id="calculator-mcp-service",
        client_secret=SERVICE_SECRET,
        client_type=model.CLIENT_CONFIDENTIAL,
        authorization_grant_type=model.GRANT_CLIENT_CREDENTIALS,
    )
    return {"user": user, "service": service, "metadata": metadata}


def basic_auth():
    value = f"calculator-mcp-service:{SERVICE_SECRET}".encode()
    return "Basic " + base64.b64encode(value).decode()


def authorization_params(**changes):
    challenge = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=")
    return {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": "calculator:execute",
        "state": "local-test-state",
        "code_challenge": challenge.decode(),
        "code_challenge_method": "S256",
        "resource": RESOURCE,
        **changes,
    }


def mint_token(user, **changes):
    client = Client()
    client.force_login(user)
    params = authorization_params(**changes)
    page = client.get("/o/authorize/", params, secure=True)
    assert page.status_code == 200, page.content[:500]
    consent = client.post("/o/authorize/", {**params, "allow": True}, secure=True)
    assert consent.status_code == 302, consent.content[:500]
    callback = parse_qs(urlsplit(consent.url).query)
    assert callback["iss"] == [ISSUER]
    assert callback["state"] == ["local-test-state"]
    token_response = client.post(
        "/o/token/",
        {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": callback["code"][0],
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
            "resource": params["resource"],
        },
        secure=True,
    )
    assert token_response.status_code == 200, token_response.content[:500]
    return token_response.json()
