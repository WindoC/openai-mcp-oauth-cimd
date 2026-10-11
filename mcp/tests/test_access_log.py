import json
import logging

import httpx
import pytest

from calculator_dot.config import Settings
from calculator_dot.server import AccessFormatter, create_app


@pytest.mark.parametrize(
    "method,path,status",
    [
        ("GET", "/healthz", 200),
        ("POST", "/mcp", 401),
        ("GET", "/.well-known/oauth-protected-resource/mcp", 200),
    ],
)
async def test_access_log_records_response_without_request_secrets(caplog, method, path, status):
    config = Settings(_env_file=None, introspection_client_secret="test-service-secret")
    app = create_app(config)
    caplog.set_level(logging.INFO, logger="calculator.access")
    async with (
        app.lifespan(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://calculator-cimd.example.com"
        ) as client,
    ):
        response = await client.request(
            method,
            path + "?token=private-query",
            headers={"X-Test-Secret": "private-header"},
        )
    assert response.status_code == status
    records = [r for r in caplog.records if r.name == "calculator.access"]
    assert len(records) == 1
    data = json.loads(AccessFormatter().format(records[0]))
    assert data["method"] == method
    assert data["path"] == path
    assert data["status"] == status
    assert data["latency_ms"] >= 0
    assert "private-query" not in caplog.text
    assert "private-header" not in caplog.text
