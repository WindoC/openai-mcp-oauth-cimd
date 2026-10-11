import json

import httpx
import pytest
from asgiref.sync import sync_to_async
from calculator_dot.auth import DjangoTokenVerifier
from calculator_dot.config import Settings
from calculator_dot.server import AuditFormatter, create_app
from django.test import Client

from tests.conftest import ISSUER, RESOURCE, SERVICE_SECRET, mint_token


def config():
    return Settings(
        _env_file=None,
        introspection_client_secret=SERVICE_SECRET,
        mcp_public_url=RESOURCE,
        django_issuer_url=ISSUER,
        django_introspection_url="https://oauth-poc.example.com/mcp-oauth/introspect/",
    )


@pytest.mark.django_db(transaction=True)
async def test_actual_dot_token_calls_mcp(oauth_setup, caplog):
    tokens = await sync_to_async(mint_token)(oauth_setup["user"])

    async def django_backend(request):
        response = await sync_to_async(Client().post)(
            "/mcp-oauth/introspect/",
            request.content.decode(),
            content_type="application/x-www-form-urlencoded",
            secure=True,
            HTTP_AUTHORIZATION=request.headers["authorization"],
        )
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers={"Content-Type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(django_backend)) as backend:
        verifier = DjangoTokenVerifier(config(), backend)
        app = create_app(config(), verifier)
        async with (
            app.lifespan(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url=RESOURCE.removesuffix("/mcp"),
                headers={
                    "Authorization": "Bearer " + tokens["access_token"],
                    "Accept": "application/json, text/event-stream",
                },
            ) as client,
        ):

            async def rpc(method, params, request_id=1):
                return await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": method,
                        "params": params,
                    },
                )

            response = await rpc(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "local-test", "version": "1"},
                },
            )
            assert response.status_code == 200, response.text
            response = await rpc("tools/list", {})
            tool = response.json()["result"]["tools"][0]
            assert tool["name"] == "calculator"
            assert tool["_meta"]["securitySchemes"][0]["scopes"] == ["calculator:execute"]
            caplog.set_level("INFO", logger="calculator.audit")
            for operation, expected in [
                ("add", 10),
                ("subtract", 6),
                ("multiply", 16),
                ("divide", 4),
            ]:
                response = await rpc(
                    "tools/call",
                    {
                        "name": "calculator",
                        "arguments": {
                            "operation": operation,
                            "a": 8,
                            "b": 2,
                        },
                    },
                )
                assert response.status_code == 200, response.text
                assert response.json()["result"]["structuredContent"]["result"] == expected
            response = await rpc(
                "tools/call",
                {
                    "name": "calculator",
                    "arguments": {
                        "operation": "divide",
                        "a": 8,
                        "b": 0,
                    },
                },
            )
            assert (
                response.json()["result"]["structuredContent"]["error"]["code"]
                == "division_by_zero"
            )
            response = await rpc(
                "tools/call",
                {
                    "name": "calculator",
                    "arguments": {
                        "operation": "eval",
                        "a": 8,
                        "b": 2,
                    },
                },
            )
            assert response.json()["result"]["isError"] is True
            assert tokens["access_token"] not in caplog.text
            assert SERVICE_SECRET not in caplog.text
            events = [record for record in caplog.records if record.name == "calculator.audit"]
            assert events[0].user_id == str(oauth_setup["user"].pk)
            assert events[0].request_id
            audit = json.loads(AuditFormatter().format(events[0]))
            assert audit["user_id"] == str(oauth_setup["user"].pk)
            for value, expected_error in [
                ("Infinity", "non_finite_input"),
                (1e308, "non_finite_result"),
            ]:
                response = await rpc(
                    "tools/call",
                    {
                        "name": "calculator",
                        "arguments": {
                            "operation": "multiply",
                            "a": value,
                            "b": 2,
                        },
                    },
                )
                assert (
                    response.json()["result"]["structuredContent"]["error"]["code"]
                    == expected_error
                )
            # Delete through the actual Django revoke endpoint; the next MCP call must reject.
            await sync_to_async(Client().post)(
                "/o/revoke_token/",
                {
                    "client_id": tokens.get("client_id", "https://chatgpt.com/oauth/client.json"),
                    "token": tokens["access_token"],
                },
                secure=True,
            )
            response = await rpc(
                "tools/call",
                {
                    "name": "calculator",
                    "arguments": {
                        "operation": "add",
                        "a": 1,
                        "b": 2,
                    },
                },
            )
            assert response.status_code == 401
