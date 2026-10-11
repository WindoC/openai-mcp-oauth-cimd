# ChatGPT acceptance

Deploy OAuth at https://oauth-poc.example.com/ and MCP at
https://calculator-cimd.example.com/mcp, with fresh test credentials and TLS.

Verify MCP /.well-known/oauth-protected-resource/mcp advertises the standalone
issuer. Verify the AS /.well-known/oauth-authorization-server advertises S256,
CIMD, none, calculator:execute and no registration_endpoint.
Use the real client metadata URL/callback supplied by the connector, not test fixtures.

Add the HTTPS Calculator MCP using OAuth, log in with the isolated Django test user,
approve calculator:execute, and call 8 + 2 and 8 / 0. Check structured results,
refresh, then revoke the token and confirm the next call fails.
Record sanitized requests/results; never include service secrets or bearer tokens.
DCR is intentionally disabled; do not open it to work around a failed CIMD request.

If authorization shows "Invalid client_id parameter value", run
`python manage.py diagnose_cimd` inside the deployed Django container. This prints
active DOT/settings, DNS addresses and hardened fetch/metadata validation results,
without querying or changing the DB. CIMD INFO failures are now visible in container
logs. Do not disable SSRF checks to accept private/fake DNS addresses; correct the
container DNS/egress configuration. DOT backs failed resolutions off for 60 seconds
by default, so wait for that interval after correcting the network before retrying.

If your network requires an explicitly trusted private SNI relay, use its IP:

```powershell
$env:CIMD_CHATGPT_SNI_PROXY_IP='192.168.1.10' # Example only: replace with your relay IP.
uv run python manage.py diagnose_cimd
uv run python manage.py runserver 127.0.0.1:8000
```

Set the variable in the same terminal before restarting runserver. This opt-in
transport is limited to the exact https://chatgpt.com/oauth/client.json URL,
port 443 and the configured private IP. It validates TLS as chatgpt.com, disables
redirects/retries and retains DOT's bounded JSON parser. All other CIMD URLs still
use SafeMetadataFetcher. It does not change system DNS or enable general private
client URL access. Live relay metadata validation and ChatGPT authorization have
been verified on the original PoC deployment.

If token exchange returns 200 but introspection returns 401, verify the dedicated
service credentials, not the ChatGPT CIMD client. Django admin shows a hashed
client secret; never paste that hash into MCP as its secret. Keep the original
random secret in MCP and let Django hash it. Changing hash_client_secret does not
recover the original secret from an existing hash.

The endpoint verifies the actual stored hash with check_password; the model flag
only controls hashing on future secret writes. Plaintext stored credentials are
still rejected. After updating mcp/.env, restart MCP. If an old environment variable
overrides the file, clear it in that MCP terminal:

```powershell
Remove-Item Env:INTROSPECTION_CLIENT_SECRET -ErrorAction SilentlyContinue
uv run calculator-mcp
```

If ChatGPT reports authentication succeeded but action discovery failed, inspect
the MCP access status and calculator.auth rejection reason. A 503 points to
introspection transport/service authentication; a 401 with inactive points to
Django token validation. Django logs only the reason and expected resource, not
tokens. Check that the running AS MCP_PUBLIC_URL is the public Calculator URL,
not a leftover localhost resource from initial local tests. Other MCP reasons
identify issuer/audience/scope/expiry failures. HTTP 200 with a JSON-RPC error
instead requires examining initialize/tools/list protocol responses.

Local tests mock CIMD network fetch but run DOT parsing, Django login/consent,
PKCE/token/refresh/revoke and actual MCP RPC. A live ChatGPT Calculator call has
succeeded. Repeat acceptance checks for your own deployment. After correcting
connection settings, refresh or recreate the ChatGPT connection if it retains stale state.
