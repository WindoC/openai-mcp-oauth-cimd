# Calculator MCP

An independent FastMCP runtime with its own lockfile, Dockerfile, deployment
examples and tests. Run `uv sync --locked`, configure the service secret using
`.env.example` as a reference, then run `uv run calculator-mcp`.
The example issuer is `https://oauth-poc.example.com/` and the resource is
`https://calculator-cimd.example.com/mcp`; replace them with your deployment URLs.

`uv run python -m pytest` uses only the MCP environment. The root test suite covers
integration between Django and MCP.

The console shows JSON HTTP access logs with method, path, status and latency_ms,
including unauthorized requests, discovery and health checks. Query strings,
headers and bodies are omitted. Calculator usage is logged by `calculator.audit`.
