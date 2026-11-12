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

The secrets are mounted read-only at `/run/secrets` (the image sets `UUDEX_SECRETS_DIR` to it). The default Docker bridge is not safe: a server started without `--network` is reachable from the host and from every other container on that bridge. Put the proxy and the database on the internal network too, since it has no outside access. The host itself can still reach the container's address on that network, so keep untrusted users off the host.

- Each secret file (`postgres_dsn`, `messagebus_connection`) must be readable by uid 10001; owner 10001 and mode 0400 is recommended.
- Use absolute paths for any setting you give the container. Relative paths resolve inside the virtualenv there, not in this directory.
- SQLite is for tests only; the image has no SQLite driver and will not start with it.
- Never publish port 8000. Only the verifying proxy may reach it, over an internal network. The image listens on all addresses, so on a network shared with other containers, pass `--host <one address>` to uvicorn as `compose.yaml` does.

## Compose

`compose.yaml` starts the server and PostgreSQL. The values in the example files are for local development only. They are not for real deployment.

1. Copy the examples (each secret is one file, mounted under `/run/secrets`; none goes in `environment:` or on a command line). Existing copies are kept, so it is safe to run this again:

       [ -e .env.compose ] || cp .env.compose.example .env.compose
       for n in postgres_password postgres_dsn messagebus_connection x_ssl_cert; do
         [ -e secrets/compose_$n ] || cp secrets/example.compose_$n secrets/compose_$n
       done

2. Edit the copies. The password in `compose_postgres_password` and the one inside `compose_postgres_dsn` must match; the DSN host is `db`.
3. Lock the files. They must be readable by uid 10001 (the server) and root (PostgreSQL). Compose cannot set file secret owners, so mode 0444 inside a 0700 directory keeps other host users out. To edit a file later, `chmod u+w` it first.

       chmod 0444 secrets/compose_*
       chmod 0700 secrets

4. Start and stop. `--wait` makes the command exit non-zero if a service is not healthy within 120 seconds; plain `up -d` exits 0 even when the server crash-loops:

       docker compose --env-file .env.compose up --build -d --wait --wait-timeout 120
       docker compose --env-file .env.compose down

The database has a pinned image, a 512 MB limit and a healthcheck, and the server waits for it. The server publishes no port. It sits on the `app` network (for the verifying proxy, which a later change adds) and on the `db` network with PostgreSQL; both networks are internal. Uvicorn listens only on the server's fixed `app` address (172.29.77.10), so PostgreSQL and any other container on `db` cannot reach it. If that subnet clashes with yours, change it in `compose.yaml` together with the `command` and the healthcheck. The host can still reach the server's `app` address, so keep untrusted users off the host. RabbitMQ is not part of this stack; the `messagebus_connection` example is only a placeholder.

The database password takes effect only when the `db_data` volume is first created. Editing `compose_postgres_password` later does not change the role's password; the old one keeps working. To change it, run `ALTER ROLE` in the running database, then update both secret files to match and recreate the server:

    docker compose --env-file .env.compose exec db psql -U postgres_user -d uudex -c "ALTER ROLE postgres_user PASSWORD 'new-password'"

Or run `docker compose --env-file .env.compose down -v`, which deletes the database and starts clean. Do not leave a real password in your shell history.

"Healthy" for the server means only that it answers HTTP on `/openapi.json`. It does not show that the database is reachable or usable.

## PostGresql Setup

See (database-layer/README.md) for instructions on setting up the database using docker.

## Generating the client

1. Make sure you have activated the server code.
2. cd to the 'generated-client-api' directory.
3. Execute 'openapi-python-client update --path openapi.json'

## Updating the openapi.json file

1. Open a browser to the Swagger UI (<https://localhost/api/docs>)
2. Click on </api/openapi.json> under the title of UUDEX API.
