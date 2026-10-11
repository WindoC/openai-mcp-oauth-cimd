import json
from unittest.mock import Mock, patch

import pytest
from django.test import override_settings
from oauth2_provider.cimd import CIMDError
from poc_oauth.cimd import CHATGPT_CLIENT_ID, ChatGPTMetadataFetcher, validate_sni_proxy_ip

from tests.conftest import REDIRECT


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "169.254.169.254",
        "1.1.1.1",
        "proxy.example",
        "::1",
        "224.0.0.1",
    ],
)
def test_proxy_must_be_explicit_private_infrastructure(address):
    with pytest.raises(CIMDError):
        validate_sni_proxy_ip(address)


@override_settings(CIMD_CHATGPT_SNI_PROXY_IP="192.168.1.10")
def test_only_exact_chatgpt_metadata_url_uses_proxy():
    metadata = {"token_endpoint_auth_method": "none"}
    fetcher = ChatGPTMetadataFetcher()
    with (
        patch.object(fetcher, "fetch_chatgpt_via_sni_proxy", return_value=(metadata, 300)) as relay,
        patch(
            "oauth2_provider.cimd.SafeMetadataFetcher.fetch", return_value=(metadata, 300)
        ) as safe,
    ):
        fetcher.fetch(CHATGPT_CLIENT_ID)
        relay.assert_called_once_with("192.168.1.10")
        safe.assert_not_called()
        for url in [
            CHATGPT_CLIENT_ID + "?x=1",
            "https://chatgpt.com/other.json",
            "https://evil.example/oauth/client.json",
            "http://chatgpt.com/oauth/client.json",
        ]:
            fetcher.fetch(url)
        assert safe.call_count == 4
        assert relay.call_count == 1


@override_settings(CIMD_CHATGPT_SNI_PROXY_IP="192.168.1.10")
def test_proxy_keeps_tls_identity_and_bounded_json_validation():
    metadata = {
        "client_id": CHATGPT_CLIENT_ID,
        "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": "private_key_jwt",
        "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
    }
    response = Mock(status=200, headers={"Content-Type": "application/json"})
    response.read.return_value = json.dumps(metadata).encode()
    with patch("poc_oauth.cimd.urllib3.HTTPSConnectionPool") as factory:
        pool = factory.return_value
        pool.urlopen.return_value = response
        result, age = ChatGPTMetadataFetcher().fetch(CHATGPT_CLIENT_ID)
        args = factory.call_args.kwargs
        assert args["host"] == "192.168.1.10"
        assert args["server_hostname"] == args["assert_hostname"] == "chatgpt.com"
        assert args["ssl_context"].check_hostname
        assert args["retries"] is False
        assert pool.urlopen.call_args.args == ("GET", "/oauth/client.json")
        assert pool.urlopen.call_args.kwargs["redirect"] is False
        assert pool.urlopen.call_args.kwargs["headers"]["Host"] == "chatgpt.com"
        assert result["token_endpoint_auth_method"] == "none"
        response.read.assert_called_once_with(16385)
        response.close.assert_called_once()
        pool.close.assert_called_once()


@override_settings(CIMD_CHATGPT_SNI_PROXY_IP="192.168.1.10")
def test_proxy_refuses_redirect():
    with patch("poc_oauth.cimd.urllib3.HTTPSConnectionPool") as factory:
        factory.return_value.urlopen.return_value = Mock(status=302)
        with pytest.raises(CIMDError, match="HTTP 302"):
            ChatGPTMetadataFetcher().fetch(CHATGPT_CLIENT_ID)
        factory.return_value.close.assert_called_once()
