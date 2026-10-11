# Standalone scope

This implementation uses Django's builtin User/LoginView, DOT OAuth, isolated
SQLite and one Calculator resource. Django owns the users and OAuth clients;
the MCP service validates tokens through its authenticated introspection endpoint.

Out of scope: multiple MCPs, social login, signup/email verification, OIDC ID tokens,
production user migration, HA databases and production rollout.
