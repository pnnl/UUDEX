# UUDEX-Server

This server implementation uses FastAPI as its basis for data access.

The example secrets, passwords and database role in this directory are for local development only. They are not for real deployment.

**Warning:** the server takes client identity from the `X-Client-Cert-*` headers. Run it only behind a proxy that verifies client certificates and overwrites those headers. Do not expose it directly.

See (DEVLIST.md) for features and status of project

## URLS for this site

- (<https://localhost/api/docs>) Swaggar UI - It validates that you have a correct tls certificate
before allowing you to see anything.  NOTE: The client must have the ca and certificate key in the
browser before going to this site.

## Configuration

Settings come from, in order of priority: environment variables, a `.env` file (if present), the files in `secrets/`, then defaults.

1. Copy `.env.example` to `.env` and set `X_SSL_CERT`.
2. Copy `secrets/example.postgres_dsn` to `secrets/postgres_dsn` and `secrets/example.messagebus_connection` to `secrets/messagebus_connection`, one value per file, and edit them. This is the recommended way. The database URL must use the async driver (`postgresql+asyncpg://`).
3. Environment variables are allowed, but are visible to the same user and to root through `/proc/<pid>/environ`.
4. Never pass a secret as a command-line argument; `ps` shows it.

`UUDEX_SETTINGS` and `UUDEX_SECRETS_DIR` name another env file or secrets directory. A name that does not exist stops startup with an error. Relative paths are relative to this directory.

Start the server (no secrets on the command line):

    uvicorn uudex_server.main:app --host 127.0.0.1 --port 8000

The tests read `tests/.env.test` only.

## Container

Build, from this directory:

    docker build -t uudex-server .

Create an internal network shared only with the verifying proxy, then run the server on it:

    docker network create --internal uudex-internal
    docker run --rm --network uudex-internal --read-only --tmpfs /tmp --memory 512m \
      -e X_SSL_CERT=... -v /path/to/secrets:/run/secrets:ro uudex-server

The secrets are mounted read-only at `/run/secrets` (the image sets `UUDEX_SECRETS_DIR` to it). The default Docker bridge is not safe: a server started without `--network` is reachable from the host and from every other container on that bridge. Put the proxy and the database on the internal network too, since it has no outside access.

- Each secret file (`postgres_dsn`, `messagebus_connection`) must be readable by uid 10001; owner 10001 and mode 0400 is recommended.
- Use absolute paths for any setting you give the container. Relative paths resolve inside the virtualenv there, not in this directory.
- SQLite is for tests only; the image has no SQLite driver and will not start with it.
- Never publish port 8000. Only the verifying proxy may reach it, over an internal network.

## PostGresql Setup

See (database-layer/README.md) for instructions on setting up the database using docker.

## Generating the client

1. Make sure you have activated the server code.
2. cd to the 'generated-client-api' directory.
3. Execute 'openapi-python-client update --path openapi.json'

## Updating the openapi.json file

1. Open a browser to the Swagger UI (<https://localhost/api/docs>)
2. Click on </api/openapi.json> under the title of UUDEX API.
