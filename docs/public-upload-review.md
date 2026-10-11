# Public upload review — openai-mcp-oauth-cimd

Reviewed 2026-10-11. Publish the Git commit, not the working directory wholesale.

## Actual sensitive files: exclude

| Path | Finding |
| --- | --- |
| mcp/.env | Actual INTROSPECTION_CLIENT_SECRET, not a test placeholder |
| django/poc.sqlite3 | User/password hash, active session, OAuth client secrets/hashes and access/refresh tokens |
| poc.sqlite3 | Old local database artifact; exclude even though inspected sensitive tables were absent |

The local Django DB contains authentication and OAuth records. Values were not
printed or copied. All database files and sidecars are excluded from publication.

Also exclude all .venv, .uv-cache, __pycache__, test/lint caches, collected static
files and dist. Old distributions had no .env/database/key/log filenames, but are
obsolete and should not be uploaded with this source tree.

## Reviewed source and examples

The final publication scan covers all Git publication candidates, including
lockfiles, templates, configuration examples and tests. Pattern checks cover
provider API keys, private keys, JWT values and encoded password literals.
Exact-match checks compare local environment credentials and database credential
values against publication candidates without printing those values.

Credential-like literals in tests are fake fixtures. The credential URL in
mcp/tests/test_mcp.py is an intentional negative URL-validation test.
The deployment Secret example is empty; .env.example secret fields are empty.
Local-development/test Django keys are explicitly non-production defaults.

This is a focused local scan, not a guarantee against every possible secret format.
This is the repository's first commit; there is no earlier committed history to audit.

## Public documentation

- Public documents are in English and use example.com deployment hosts.
- SNI relay documentation and tests use a generic private example IP;
  the original private relay IP and internal DNS alias have been removed.
- Setup instructions use paths relative to the checkout. Historical integration documents in
  docs/archive are retained locally and excluded by .gitignore; omit them from
  browser uploads and manually created ZIPs too. They describe an older design
  and are not dependencies of this standalone PoC.

## Upload safely

.gitignore was expanded for .env variants (keeping example templates), database
sidecars/backups, logs and key files. Existing exclusions already covered the
known .env/SQLite files and generated directories.

Git honors .gitignore when adding new untracked files. GitHub browser folder upload
and a manually created ZIP do not automatically apply this policy. A tracked secret
would also remain tracked despite .gitignore, so inspect the selected files before
publishing. Avoid uploading the whole folder through the browser.

Publish source/config examples/lockfiles/tests and intended documentation only.
Keep runtime secrets and databases local. If any actual secret or database was
previously made public, rotate/revoke affected credentials and sessions/tokens;
removing a file afterwards does not erase the exposure.

No runtime credentials were rotated or deleted by this publication review.
The publication commit contains source, examples, tests and documentation only.
