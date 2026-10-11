# Standalone PoC verification — 2026-10-11

- Root Django/integration suite: 38 passed on Python 3.12 / Django 6.0.6 / DOT 3.4.1.
- MCP independent environment: 28 tests passed; no Django installation required.
- Ruff checks passed for Django, MCP and integration tests.
- Standalone Django check and migration: passed; new django/poc.sqlite3 only.
- Real loopback HTTP E2E with independent django/.venv and mcp/.venv processes:
  builtin login, S256 token exchange, Calculator 8 + 2 = 10, revocation then 401.
  This test uses a temporary PoC DB and stops both processes afterwards.
- Tests cover builtin Django login/consent, CIMD parsing/allowlist, S256/code replay,
  refresh, expiry/revocation, inactive users, resource/scope, service authentication,
  public MCP discovery, Calculator operations/errors/audit and revocation after RPC.
- Old allauth/email-verification/blocked-custom-user tests are no longer applicable.

CIMD HTTP fetch is mocked in integration tests. Tests use a dedicated PoC database.
Docker image builds remain unverified. The user confirmed a successful public
ChatGPT connection and Calculator call: 123 × 789 = 97,047.

## CIMD failure diagnosis

On the original PoC host, system DNS routed chatgpt.com to a private SNI relay.
SafeMetadataFetcher rejected this non-public address before fetching metadata.
A read-only public DNS query returned public Cloudflare addresses instead.
No system DNS settings were changed.
Added read-only diagnose_cimd and INFO logging to report runtime fetch failures.

The deployment required retaining the relay. Added explicit
CIMD_CHATGPT_SNI_PROXY_IP support pinned to the exact ChatGPT metadata URL, with
TLS identity/verification, no redirects and bounded parsing retained.
Live fetch through the private relay passed, returning valid metadata with negotiated
none method. Direct public IP fetch returned 403. No system DNS was modified.
Added tests for fixed-path routing, private relay IP validation, TLS identity,
response limits and redirect rejection. Live ChatGPT authorization later succeeded.

## Introspection credential correction

User logs showed successful authorization/token exchange followed by introspection
401. The MCP configuration contained the stored Django hash instead of the raw
service secret; its hashing flag was also off. Rotated only the isolated PoC
service credential, updated mcp/.env and stored its hash in Django, without printing
the credential or changing ChatGPT clients/user tokens. The running Django returned
200 with active=false for a deliberately nonexistent token using the new credential,
confirming service authentication. MCP requires a restart to load an updated secret.
Added regressions for hash verification with a disabled future-hashing flag and
rejection of plaintext stored credentials.

## Action discovery failure

Live MCP returned invalid_token/inactive after successful OAuth. An authenticated
localhost diagnostic request confirmed running Django expected
https://oauth-poc.example.com/mcp while token/MCP resource was
https://calculator-cimd.example.com/mcp (URLs anonymized for this public report).
Both services must use the same MCP_PUBLIC_URL, with the issuer set separately.
Recreating the ChatGPT connection resolved the reported discovery failure;
the user confirmed 123 × 789 = 97,047. Further diagnosis was stopped at that point.
Inactive response diagnostic headers are service-authenticated and contain only
reason/expected resource; JSON remains active:false. No token/secret is logged.
