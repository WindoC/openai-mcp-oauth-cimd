# Pinned PoC dependencies

Django 6.0.6, django-oauth-toolkit 3.4.1, Python 3.12 and FastMCP 3.4.8 are pinned.
The standalone AS uses oauthlib 3.3.1 and jwcrypto 1.5.7 constraints to retain the
tested protocol behavior. Each service's uv.lock records its transitive dependencies.

New SQLite migration applies DOT 0001–0022 alongside Django auth/admin/session
tables in the dedicated PoC database. CIMD is enabled with a public-method adapter
because released DOT 3.4.1 does not support private_key_jwt CIMD.

Start this independent PoC with a new database and fresh credentials.
