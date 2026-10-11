import ipaddress
import ssl

import urllib3
from django.conf import settings
from oauth2_provider.cimd import CIMDError, SafeMetadataFetcher
from oauth2_provider.settings import oauth2_settings

CHATGPT_CLIENT_ID = "https://chatgpt.com/oauth/client.json"


def validate_sni_proxy_ip(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise CIMDError("SNI proxy must be an explicit private IP address") from exc
    private_networks = (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "fc00::/7",
    )
    if not any(address in ipaddress.ip_network(network) for network in private_networks):
        raise CIMDError("SNI proxy IP must be RFC1918 or IPv6 ULA")
    return str(address)


def negotiate_public_method(metadata):
    """Negotiate the supported public method while preserving DOT's validation."""
    result = dict(metadata)
    selected = result.get("token_endpoint_auth_method", "none")
    if "token_endpoint_auth_methods_supported" in result:
        methods = result["token_endpoint_auth_methods_supported"]
        if (
            not isinstance(methods, list)
            or not methods
            or not all(isinstance(method, str) for method in methods)
            or "none" not in methods
            or selected not in methods
            or selected not in {"none", "private_key_jwt"}
        ):
            raise CIMDError("No supported public client authentication method")
        result["token_endpoint_auth_method"] = "none"
    elif result.get("token_endpoint_auth_method", "none") != "none":
        raise CIMDError("Only public clients with PKCE are supported")
    return result


class ChatGPTMetadataFetcher(SafeMetadataFetcher):
    def fetch(self, client_id):
        proxy_ip = getattr(settings, "CIMD_CHATGPT_SNI_PROXY_IP", "")
        if proxy_ip and client_id == CHATGPT_CLIENT_ID:
            metadata, max_age = self.fetch_chatgpt_via_sni_proxy(proxy_ip)
        else:
            metadata, max_age = super().fetch(client_id)
        return negotiate_public_method(metadata), max_age

    def fetch_chatgpt_via_sni_proxy(self, proxy_ip):
        # Explicitly trusted infrastructure, not an exception for client-supplied
        # private URLs. Destination IP, TLS identity and request path are pinned.
        proxy_ip = validate_sni_proxy_ip(proxy_ip)
        timeout = oauth2_settings.CIMD_FETCH_TIMEOUT_SECONDS
        pool = urllib3.HTTPSConnectionPool(
            host=proxy_ip,
            port=443,
            server_hostname="chatgpt.com",
            assert_hostname="chatgpt.com",
            ssl_context=ssl.create_default_context(),
            timeout=urllib3.Timeout(connect=timeout, read=timeout, total=timeout),
            retries=False,
            maxsize=1,
        )
        try:
            response = pool.urlopen(
                "GET",
                "/oauth/client.json",
                headers={"Host": "chatgpt.com", "Accept": "application/json"},
                redirect=False,
                preload_content=False,
            )
            try:
                return self._read_document(response)
            finally:
                response.close()
        except urllib3.exceptions.HTTPError as exc:
            raise CIMDError(f"ChatGPT metadata through SNI proxy failed: {exc}") from exc
        finally:
            pool.close()
