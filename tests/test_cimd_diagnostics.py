from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from oauth2_provider.cimd import CIMDError

from tests.conftest import CLIENT_ID, REDIRECT


def test_diagnostics_validate_real_metadata_shape_without_db():
    metadata = {
        "client_id": CLIENT_ID,
        "client_name": "ChatGPT",
        "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": "private_key_jwt",
        "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "jwks_uri": "https://chatgpt.com/oauth/jwks.json",
        "token_endpoint_auth_signing_alg": "RS256",
    }
    output = StringIO()
    with (
        patch("poc_oauth.management.commands.diagnose_cimd.socket.getaddrinfo", return_value=[]),
        patch("oauth2_provider.cimd.SafeMetadataFetcher.fetch", return_value=(metadata, 300)),
    ):
        call_command("diagnose_cimd", stdout=output)
    assert "Negotiated method: none" in output.getvalue()
    assert "no Application row or token was created" in output.getvalue()


def test_diagnostics_report_fetch_rejection_without_db():
    with (
        patch("poc_oauth.management.commands.diagnose_cimd.socket.getaddrinfo", return_value=[]),
        patch(
            "oauth2_provider.cimd.SafeMetadataFetcher.fetch",
            side_effect=CIMDError("client_id host resolves to a non-public address"),
        ),
        pytest.raises(CommandError, match="non-public address"),
    ):
        call_command("diagnose_cimd", stdout=StringIO())
