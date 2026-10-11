from django.contrib.auth.hashers import check_password
from django.test import override_settings

from tests.conftest import SERVICE_SECRET, basic_auth


def test_stored_hash_is_verified_even_if_future_hashing_flag_is_off(oauth_setup, client):
    application = oauth_setup["service"]
    assert check_password(SERVICE_SECRET, application.client_secret)
    application.hash_client_secret = False
    application.save(update_fields=["hash_client_secret"])
    response = client.post(
        "/mcp-oauth/introspect/",
        {"token": "unknown-test-token"},
        HTTP_AUTHORIZATION=basic_auth(),
    )
    assert response.status_code == 200
    assert response.json() == {"active": False}
    assert response["X-PoC-Introspection-Reason"] == "unknown_token"


@override_settings(MCP_RESOURCE_URI="https://oauth-poc.example.com/mcp")
def test_diagnostic_headers_report_running_resource_without_secrets(oauth_setup, client):
    response = client.post(
        "/mcp-oauth/introspect/",
        {"token": "private-test-token"},
        HTTP_AUTHORIZATION=basic_auth(),
    )
    assert response.status_code == 200
    assert response.json() == {"active": False}
    assert response["X-PoC-Expected-Resource"] == "https://oauth-poc.example.com/mcp"
    assert response["X-PoC-Introspection-Reason"] == "unknown_token"
    assert "private-test-token" not in str(dict(response.headers))
    assert SERVICE_SECRET not in str(dict(response.headers))


def test_plaintext_stored_secret_is_not_accepted(oauth_setup, client):
    application = oauth_setup["service"]
    type(application).objects.filter(pk=application.pk).update(
        hash_client_secret=False,
        client_secret=SERVICE_SECRET,
    )
    response = client.post(
        "/mcp-oauth/introspect/",
        {"token": "unknown-test-token"},
        HTTP_AUTHORIZATION=basic_auth(),
    )
    assert response.status_code == 401
