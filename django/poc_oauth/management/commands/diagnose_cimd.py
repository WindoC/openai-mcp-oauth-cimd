"""Read-only CIMD diagnosis from the server's own DNS/network/settings."""

import importlib.metadata
import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from oauth2_provider.cimd import CIMDError, _build_application_kwargs
from oauth2_provider.settings import oauth2_settings


class Command(BaseCommand):
    help = "Check ChatGPT CIMD fetch and validation without registering clients or changing the DB"
    requires_system_checks = []

    def handle(self, *args, **options):
        client_id = "https://chatgpt.com/oauth/client.json"
        self.stdout.write(f"DOT version: {importlib.metadata.version('django-oauth-toolkit')}")
        self.stdout.write(f"CIMD enabled: {oauth2_settings.CIMD_ENABLED}")
        self.stdout.write(f"CIMD allowed hosts: {oauth2_settings.CIMD_ALLOWED_HOSTS}")
        fetcher_class = oauth2_settings.CIMD_METADATA_FETCHER
        self.stdout.write(f"Fetcher: {fetcher_class.__module__}.{fetcher_class.__name__}")
        proxy_ip = getattr(settings, "CIMD_CHATGPT_SNI_PROXY_IP", "")
        self.stdout.write(f"Trusted ChatGPT SNI proxy: {proxy_ip or 'disabled'}")
        if not oauth2_settings.CIMD_ENABLED:
            raise CommandError("CIMD is disabled in the active settings")
        if (
            not all(
                permission().has_permission(None, client_id)
                for permission in oauth2_settings.CIMD_REGISTRATION_PERMISSION_CLASSES
            )
            or not oauth2_settings.CIMD_REGISTRATION_PERMISSION_CLASSES
        ):
            raise CommandError("Active CIMD registration permissions reject the ChatGPT client")
        try:
            addresses = sorted(
                {
                    result[4][0]
                    for result in socket.getaddrinfo("chatgpt.com", 443, type=socket.SOCK_STREAM)
                }
            )
            for address in addresses:
                self.stdout.write(
                    f"DNS: {address} (global={ipaddress.ip_address(address).is_global})"
                )
            metadata, max_age = fetcher_class().fetch(client_id)
            if metadata.get("client_id") != client_id:
                raise CIMDError("document client_id does not match the requested URL")
            kwargs = _build_application_kwargs(metadata)
        except (CIMDError, socket.gaierror) as exc:
            raise CommandError(f"CIMD fetch/validation failed: {exc}") from exc
        self.stdout.write(
            f"Negotiated method: {metadata.get('token_endpoint_auth_method', 'none')}"
        )
        self.stdout.write(f"Metadata cache age: {max_age}")
        self.stdout.write(f"Grant type: {kwargs['authorization_grant_type']}")
        redirects = metadata["redirect_uris"]
        self.stdout.write(
            f"Redirect hosts: {sorted({urlsplit(uri).hostname for uri in redirects})}"
        )
        self.stdout.write(
            self.style.SUCCESS(
                "CIMD fetch and metadata validation passed; no Application row or token was created"
            )
        )
