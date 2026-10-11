import json
import logging
import math
import operator
import time
import uuid
from typing import Literal
from urllib.parse import urlsplit

import uvicorn
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.dependencies import get_access_token
from pydantic import AnyHttpUrl
from starlette.responses import JSONResponse

from calculator_dot.auth import DjangoTokenVerifier, IdentityUnavailable
from calculator_dot.config import Settings

log = logging.getLogger("calculator.audit")
access_log = logging.getLogger("calculator.access")
OPERATIONS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


def create_server(config: Settings, verifier=None) -> FastMCP:
    origin = urlsplit(config.mcp_public_url)
    auth = RemoteAuthProvider(
        token_verifier=verifier or DjangoTokenVerifier(config),
        authorization_servers=[AnyHttpUrl(config.django_issuer_url)],
        base_url=f"{origin.scheme}://{origin.netloc}",
        scopes_supported=[config.mcp_required_scope],
    )
    server = FastMCP("Django OAuth Calculator", auth=auth)

    @server.tool(
        name="calculator",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        meta={"securitySchemes": [{"type": "oauth2", "scopes": [config.mcp_required_scope]}]},
    )
    def calculator(
        operation: Literal["add", "subtract", "multiply", "divide"], a: float, b: float
    ) -> dict:
        """Calculate with two finite numbers. Requires Django OAuth sign-in."""
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        token = get_access_token()
        if token is None or config.mcp_required_scope not in token.scopes or not token.subject:
            raise ToolError("OAuth authorization required")
        outcome = "error"
        try:
            if not math.isfinite(a) or not math.isfinite(b):
                return {"error": {"code": "non_finite_input", "message": "Use finite numbers"}}
            if operation == "divide" and b == 0:
                return {"error": {"code": "division_by_zero", "message": "Cannot divide by zero"}}
            result = OPERATIONS[operation](a, b)
            if not math.isfinite(result):
                return {"error": {"code": "non_finite_result", "message": "Result exceeds limits"}}
            outcome = "success"
            return {"operation": operation, "operands": {"a": a, "b": b}, "result": result}
        finally:
            log.info(
                "calculator_usage",
                extra={
                    "request_id": request_id,
                    "user_id": token.subject,
                    "oauth_client": token.client_id,
                    "tool": "calculator",
                    "outcome": outcome,
                    "latency_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request):
        return JSONResponse({"status": "ok"})

    return server


class IdentityErrorMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        except IdentityUnavailable:
            response = JSONResponse(
                {"error": "identity_service_unavailable"},
                status_code=503,
                headers={"Retry-After": "5"},
            )
            await response(scope, receive, send)


class AccessLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.monotonic()
        status = 500

        async def capture_status(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            access_log.info(
                "http_access",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "latency_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )


class AccessFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "event": "http_access",
                **{
                    key: getattr(record, key, None)
                    for key in ("method", "path", "status", "latency_ms")
                },
            }
        )


def create_app(config: Settings, verifier=None):
    server = create_server(config, verifier)
    app = server.http_app(path="/mcp", stateless_http=True, json_response=True)
    app.add_middleware(IdentityErrorMiddleware)
    app.add_middleware(AccessLogMiddleware)
    return app


def main():
    config = Settings()
    auth_log = logging.getLogger("calculator.auth")
    auth_handler = logging.StreamHandler()
    auth_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    auth_log.addHandler(auth_handler)
    auth_log.setLevel(logging.INFO)
    auth_log.propagate = False
    auth_log.info(
        "mcp_startup issuer=%s resource=%s introspection=%s service_client=%s",
        config.django_issuer_url,
        config.mcp_public_url,
        config.django_introspection_url,
        config.introspection_client_id,
    )
    for logger, formatter in ((log, AuditFormatter()), (access_log, AccessFormatter())):
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    uvicorn.run(create_app(config), host=config.host, port=config.port, access_log=False)


class AuditFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                key: getattr(record, key, None)
                for key in (
                    "request_id",
                    "user_id",
                    "oauth_client",
                    "tool",
                    "outcome",
                    "latency_ms",
                )
            }
        )


if __name__ == "__main__":
    main()
