# Standalone PoC architecture

ChatGPT uses the Calculator's protected-resource metadata to discover the standalone
issuer https://oauth-poc.example.com/. CIMD resolves its metadata URL at the AS, where
a test user signs in using Django's builtin username/password form and approves
calculator:execute. Authorization Code + S256 issues resource-bound opaque tokens.

Calculator calls POST /mcp-oauth/introspect/ using a dedicated service client secret.
The AS checks expiry/revocation, active user, resource and scope, returning sub, iss,
client_id, scope, exp and aud. The MCP verifier checks issuer/audience/scope/expiry
again and authorizes tool execution. Service credentials and bearer tokens are not
logged. Revocation takes effect on the next introspection, without a validation cache.

This PoC intentionally supports a single MCP URL/client/scope. Django stores users,
OAuth grants/tokens and cached CIMD applications in its isolated SQLite DB. The
MCP has no DB, token files or PVC. Django has no signup/social login/ID-token flows.

CIMD allowlist is chatgpt.com; DCR is off. DOT 3.4.1's SafeMetadataFetcher supplies
HTTPS/DNS/IP/TLS/size/timeout protections. The adapter negotiates none only when
explicitly offered; it rejects unsupported/shared-secret methods. Pin upgrades
rather than relying on newer capabilities described by latest documentation.

Django's locmem CIMD backoff is process-local; the deployment uses one worker and
one replica. Add ingress rate limiting. This is a functional PoC, not an HA AS.
