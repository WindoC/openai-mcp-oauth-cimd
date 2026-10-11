"""Exercise each service's own interpreter and dependency lock over real loopback HTTP."""

import base64
import hashlib
import os
import re
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def python_for(project):
    venv = ROOT / project / ".venv"
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def test_independent_process_login_and_calculator():
    assert python_for("django").is_file(), "Run uv sync --locked in django/ first"
    assert python_for("mcp").is_file(), "Run uv sync --locked in mcp/ first"
    oauth_port, mcp_port = free_port(), free_port()
    issuer = f"http://127.0.0.1:{oauth_port}/"
    resource = f"http://127.0.0.1:{mcp_port}/mcp"
    service_secret = secrets.token_urlsafe(48)
    password = secrets.token_urlsafe(32)
    verifier = "a" * 64
    redirect = "https://example.com/callback"
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "POC_LOCAL": "true",
        "POC_ALLOWED_HOSTS": "127.0.0.1",
        "POC_DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "DJANGO_ISSUER_URL": issuer,
        "MCP_PUBLIC_URL": resource,
        "INTROSPECTION_CLIENT_ID": "calculator-mcp-service",
        "INTROSPECTION_CLIENT_SECRET": service_secret,
        "SMOKE_PASSWORD": password,
        "ALLOW_LOCAL_HTTP": "true",
        "DJANGO_INTROSPECTION_URL": issuer + "mcp-oauth/introspect/",
        "HOST": "127.0.0.1",
        "PORT": str(mcp_port),
    }
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    processes = []
    # All generated DB files and recursive TemporaryDirectory cleanup stay in django/.
    with tempfile.TemporaryDirectory(prefix="process-smoke-", dir=ROOT / "django") as temp:
        env["POC_DB_PATH"] = str(Path(temp) / "smoke.sqlite3")

        def manage(*args):
            result = subprocess.run(
                [str(python_for("django")), "manage.py", *args],
                cwd=ROOT / "django",
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=flags,
            )
            assert result.returncode == 0, result.stderr

        manage("migrate", "--noinput")
        manage("create_mcp_service")
        manage(
            "shell",
            "-c",
            (
                "import os; from django.contrib.auth.models import User; "
                "from oauth2_provider.models import Application; "
                "User.objects.create_user(username='smoke', "
                "password=os.environ['SMOKE_PASSWORD']); "
                "Application.objects.create(client_id='process-smoke', client_type='public', "
                "authorization_grant_type='authorization-code', "
                "redirect_uris='https://example.com/callback')"
            ),
        )
        try:
            for project, args in [
                ("django", ["manage.py", "runserver", f"127.0.0.1:{oauth_port}", "--noreload"]),
                ("mcp", ["-m", "calculator_dot.server"]),
            ]:
                processes.append(
                    subprocess.Popen(
                        [str(python_for(project)), *args],
                        cwd=ROOT / project,
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=flags,
                    )
                )
            with httpx.Client(timeout=5, follow_redirects=False) as client:
                for url in [issuer + "healthz", resource.removesuffix("/mcp") + "/healthz"]:
                    deadline = time.monotonic() + 20
                    while True:
                        try:
                            if client.get(url).status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        assert all(p.poll() is None for p in processes), "Service exited on startup"
                        assert time.monotonic() < deadline, "Service did not become ready"
                        time.sleep(0.1)
                metadata = client.get(issuer + ".well-known/oauth-authorization-server").json()
                assert metadata["issuer"] == issuer
                login = client.get(issuer + "accounts/login/")
                csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login.text)[1]
                response = client.post(
                    issuer + "accounts/login/",
                    data={
                        "username": "smoke",
                        "password": password,
                        "csrfmiddlewaretoken": csrf,
                    },
                )
                assert response.status_code == 302
                challenge = (
                    base64.urlsafe_b64encode(
                        hashlib.sha256(verifier.encode()).digest(),
                    )
                    .rstrip(b"=")
                    .decode()
                )
                params = {
                    "client_id": "process-smoke",
                    "redirect_uri": redirect,
                    "response_type": "code",
                    "scope": "calculator:execute",
                    "resource": resource,
                    "state": "smoke-state",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
                consent = client.get(issuer + "o/authorize/", params=params)
                assert consent.status_code == 200
                csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', consent.text)[1]
                response = client.post(
                    issuer + "o/authorize/",
                    data={
                        **params,
                        "allow": "true",
                        "csrfmiddlewaretoken": csrf,
                    },
                )
                assert response.status_code == 302
                callback = parse_qs(urlsplit(response.headers["location"]).query)
                assert callback["iss"] == [issuer]
                response = client.post(
                    issuer + "o/token/",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": "process-smoke",
                        "code": callback["code"][0],
                        "redirect_uri": redirect,
                        "code_verifier": verifier,
                        "resource": resource,
                    },
                )
                assert response.status_code == 200
                token = response.json()["access_token"]
                headers = {
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json, text/event-stream",
                }
                response = client.post(
                    resource,
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "process-smoke", "version": "1"},
                        },
                    },
                )
                assert response.status_code == 200
                call = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "calculator",
                        "arguments": {"operation": "add", "a": 8, "b": 2},
                    },
                }
                response = client.post(resource, headers=headers, json=call)
                assert response.status_code == 200
                assert response.json()["result"]["structuredContent"]["result"] == 10
                response = client.post(
                    issuer + "o/revoke_token/",
                    data={
                        "client_id": "process-smoke",
                        "token": token,
                    },
                )
                assert response.status_code == 200
                assert client.post(resource, headers=headers, json=call).status_code == 401
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                process.wait(timeout=10)
