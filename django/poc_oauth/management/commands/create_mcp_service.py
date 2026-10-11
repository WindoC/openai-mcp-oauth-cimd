import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from oauth2_provider.models import get_application_model


class Command(BaseCommand):
    help = "Create the dedicated introspection service client; secret is read from environment"

    def handle(self, *args, **options):
        secret = os.environ.get("INTROSPECTION_CLIENT_SECRET", "")
        if len(secret) < 32:
            raise CommandError("Set INTROSPECTION_CLIENT_SECRET to at least 32 random characters")
        model = get_application_model()
        if model.objects.filter(client_id=settings.MCP_INTROSPECTION_CLIENT_ID).exists():
            raise CommandError("Client exists; this command does not overwrite credentials")
        model.objects.create(
            name="Calculator MCP introspection service",
            client_id=settings.MCP_INTROSPECTION_CLIENT_ID,
            client_secret=secret,
            client_type=model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=model.GRANT_CLIENT_CREDENTIALS,
        )
        self.stdout.write(self.style.SUCCESS("Service client created (secret not printed)"))
