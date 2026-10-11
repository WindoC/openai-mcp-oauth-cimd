from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client
from django.utils import timezone
from oauth2_provider.cimd import CIMDError, _build_application_kwargs
from oauth2_provider.models import get_access_token_model, get_application_model
from poc_oauth.cimd import negotiate_public_method

from tests.conftest import (
    CLIENT_ID,
    ISSUER,
    REDIRECT,
    RESOURCE,
    VERIFIER,
    authorization_params,
    basic_auth,
    mint_token,
)


def test_discovery(client):
    response = client.get("/.well-known/oauth-authorization-server", secure=True)
    assert response.status_code == 200
    data = response.json()
    assert data["issuer"] == ISSUER
    assert data["code_challenge_methods_supported"] == ["S256"]
    assert data["client_id_metadata_document_supported"] is True
    assert "none" in data["token_endpoint_auth_methods_supported"]
    assert "registration_endpoint" not in data
    assert data["authorization_response_iss_parameter_supported"] is True


def test_builtin_django_login_and_consent(oauth_setup):
    client = Client()
    params = authorization_params()
    response = client.get("/o/authorize/", params, secure=True)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url
    response = client.get(response.url, secure=True)
    assert response.status_code == 200
    response = client.post(
        "/accounts/login/",
        {
            "username": "poc-user",
            "password": "poc-password-long",
        },
        secure=True,
    )
    assert response.status_code == 302, response.content[:500]
    page = client.get("/o/authorize/", params, secure=True)
    assert page.status_code == 200
    assert b"calculator:execute" in page.content


def test_cimd_negotiation_and_identity(oauth_setup, client):
    with pytest.raises(CIMDError):
        _build_application_kwargs(oauth_setup["metadata"])
    normalized = negotiate_public_method(oauth_setup["metadata"])
    _build_application_kwargs(normalized)
    assert oauth_setup["metadata"]["token_endpoint_auth_method"] == "private_key_jwt"
    token = mint_token(oauth_setup["user"])
    response = client.post(
        "/mcp-oauth/introspect/",
        {"token": token["access_token"]},
        secure=True,
        HTTP_AUTHORIZATION=basic_auth(),
    )
    data = response.json()
    assert data["active"] is True
    assert data["sub"] == str(oauth_setup["user"].pk)
    assert data["aud"] == [RESOURCE]
    assert data["client_id"] == CLIENT_ID
    assert "username" not in data and "email" not in data
    stored = get_access_token_model().objects.get(user=oauth_setup["user"])
    assert stored.token != token["access_token"]  # hashed storage is active


@pytest.mark.parametrize("methods", [["private_key_jwt"], [], "none", ["none", 123]])
def test_cimd_rejects_unsupported_methods(methods):
    with pytest.raises(CIMDError):
        negotiate_public_method({"token_endpoint_auth_methods_supported": methods})


def test_cimd_rejects_secret(oauth_setup):
    with pytest.raises(CIMDError):
        _build_application_kwargs(
            negotiate_public_method(
                {
                    **oauth_setup["metadata"],
                    "client_secret": "invalid-shared-secret",
                }
            )
        )


@pytest.mark.parametrize(
    "change",
    [
        {"code_challenge_method": "plain"},
        {"code_challenge": "", "code_challenge_method": ""},
        {"redirect_uri": "https://evil.example/callback"},
        {"response_type": "token"},
    ],
)
def test_bad_authorization_rejected(oauth_setup, client, change):
    client.force_login(oauth_setup["user"])
    params = authorization_params(**change)
    response = client.get("/o/authorize/", params, secure=True)
    if response.status_code == 200:
        response = client.post("/o/authorize/", {**params, "allow": True}, secure=True)
    if response.status_code == 302:
        assert "code" not in parse_qs(urlsplit(response.url).query)
        assert "error" in parse_qs(urlsplit(response.url).query)
    else:
        assert response.status_code == 400


def test_wrong_pkce_and_code_replay(oauth_setup, client):
    client.force_login(oauth_setup["user"])
    params = authorization_params()
    client.get("/o/authorize/", params, secure=True)
    consent = client.post("/o/authorize/", {**params, "allow": True}, secure=True)
    code = parse_qs(urlsplit(consent.url).query)["code"][0]
    body = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "code_verifier": "b" * 64,
        "resource": RESOURCE,
    }
    assert client.post("/o/token/", body, secure=True).status_code == 400
    body["code_verifier"] = VERIFIER
    assert client.post("/o/token/", body, secure=True).status_code == 200
    assert client.post("/o/token/", body, secure=True).status_code == 400


@pytest.mark.parametrize("problem", ["expired", "revoked", "inactive", "aud", "scope"])
def test_introspection_fail_closed(oauth_setup, client, problem):
    token = mint_token(oauth_setup["user"])
    stored = get_access_token_model().objects.get(user=oauth_setup["user"])
    if problem == "expired":
        stored.expires = timezone.now() - timedelta(seconds=1)
        stored.save()
    elif problem == "revoked":
        response = client.post(
            "/o/revoke_token/",
            {
                "client_id": CLIENT_ID,
                "token": token["access_token"],
            },
            secure=True,
        )
        assert response.status_code == 200
    elif problem in {"blocked", "inactive"}:
        user = oauth_setup["user"]
        setattr(user, "is_blocked" if problem == "blocked" else "is_active", problem == "blocked")
        user.save()
    elif problem == "aud":
        stored.resource = ["https://other.example/mcp"]
        stored.save()
    elif problem == "scope":
        stored.scope = "profile"
        stored.save()
    data = client.post(
        "/mcp-oauth/introspect/",
        {"token": token["access_token"]},
        secure=True,
        HTTP_AUTHORIZATION=basic_auth(),
    ).json()
    assert data == {"active": False}


def test_service_credentials_and_userless_token(oauth_setup, client):
    token = mint_token(oauth_setup["user"])
    assert (
        client.post(
            "/mcp-oauth/introspect/", {"token": token["access_token"]}, secure=True
        ).status_code
        == 401
    )
    assert client.get("/mcp-oauth/introspect/", secure=True).status_code == 405
    stored = get_access_token_model().objects.get(user=oauth_setup["user"])
    stored.user = None
    stored.save()
    response = client.post(
        "/mcp-oauth/introspect/",
        {"token": token["access_token"]},
        secure=True,
        HTTP_AUTHORIZATION=basic_auth(),
    )
    assert response.json() == {"active": False}
    assert (
        "calculator-mcp-service"
        != get_application_model()
        .objects.get(
            client_id=CLIENT_ID,
        )
        .client_id
    )


def test_refresh_rotation(oauth_setup, client):
    first = mint_token(oauth_setup["user"])
    response = client.post(
        "/o/token/",
        {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
            "resource": RESOURCE,
        },
        secure=True,
    )
    assert response.status_code == 200, response.content[:500]
    second = response.json()
    assert second["access_token"] != first["access_token"]
    response = client.post(
        "/mcp-oauth/introspect/",
        {"token": second["access_token"]},
        secure=True,
        HTTP_AUTHORIZATION=basic_auth(),
    )
    assert response.json()["aud"] == [RESOURCE]


def test_cimd_disallows_untrusted_host(oauth_setup, client):
    client.force_login(oauth_setup["user"])
    response = client.get(
        "/o/authorize/",
        authorization_params(
            client_id="https://evil.example/client.json",
        ),
        secure=True,
    )
    assert response.status_code == 400
    assert (
        not get_application_model()
        .objects.filter(
            client_id="https://evil.example/client.json",
        )
        .exists()
    )


def test_token_exchange_rejects_other_resource(oauth_setup, client):
    client.force_login(oauth_setup["user"])
    params = authorization_params()
    client.get("/o/authorize/", params, secure=True)
    consent = client.post("/o/authorize/", {**params, "allow": True}, secure=True)
    code = parse_qs(urlsplit(consent.url).query)["code"][0]
    response = client.post(
        "/o/token/",
        {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
            "resource": "https://other.example/mcp",
        },
        secure=True,
    )
    assert response.status_code == 400
