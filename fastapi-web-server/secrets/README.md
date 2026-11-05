# Example secrets

The files here are examples for local development only. They are not for real deployment. Use your own values and keep them out of version control.

Recommended way to configure the server: one value per file in this directory.

- `example.postgres_dsn` -> copy to `postgres_dsn` (async driver required: `postgresql+asyncpg://`)
- `example.messagebus_connection` -> copy to `messagebus_connection`

Only the `example.*` files and this README are tracked; any other file here is ignored by git. Set `X_SSL_CERT` in `.env` (see `.env.example`).

Environment variables also work and take priority over files, but they are visible to the same user and to root through `/proc/<pid>/environ`. Never pass a secret on the command line, where `ps` shows it.

Relative paths are relative to the `fastapi-web-server` directory, not the current directory. `UUDEX_SETTINGS` names an env file and `UUDEX_SECRETS_DIR` names a different secrets directory; both must exist.
