# Example secrets

The files here are examples for local development only. They are not for real deployment. Use your own values and keep them out of version control.

To run the server, copy each example to the name settings read and edit it:

- `example.postgres_dsn` -> `postgres_dsn` (must use the async driver, `postgresql+asyncpg://`)
- `example.messagebus_connection` -> `messagebus_connection`

Put the certificate header in `.env` as `X_SSL_CERT=...`. Settings paths are relative to the `fastapi-web-server` directory, not the current directory. Set `UUDEX_SETTINGS` (an env file) or `UUDEX_SECRETS_DIR` to use other locations.
