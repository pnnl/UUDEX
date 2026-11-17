# UUDEX-Server

This server implementation uses FastAPI as its basis for data access.

The example secrets, passwords and database role in this directory are for local development only. They are not for real deployment.

**Warning:** the server takes client identity from the `X-Forwarded-Tls-Client-Cert` header, and believes it only from the peers listed in `TRUSTED_PROXY_HOSTS`. Run it only behind a proxy that verifies client certificates and replaces that header. Do not expose it directly.

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

    uvicorn uudex_server.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers

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

`compose.yaml` starts the server, PostgreSQL and a Traefik proxy that verifies client certificates. The values in the example files are for local development only. They are not for real deployment.

1. Copy the examples (each secret is one file, mounted under `/run/secrets`; none goes in `environment:` or on a command line). Existing copies are kept, so it is safe to run this again:

       [ -e .env.compose ] || cp .env.compose.example .env.compose
       for n in postgres_password postgres_dsn messagebus_connection x_ssl_cert; do
         [ -e secrets/compose_$n ] || cp secrets/example.compose_$n secrets/compose_$n
       done

2. Edit the copies. The password in `compose_postgres_password` and the one inside `compose_postgres_dsn` must match; the DSN host is `db`.
3. Lock the files. They must be readable by uid 10001 (the server) and root (PostgreSQL). Compose cannot set file secret owners, so mode 0444 inside a 0700 directory keeps other host users out. To edit a file later, `chmod u+w` it first.

       chmod 0444 secrets/compose_*
       chmod 0700 secrets

4. Make the certificates, as the user who will run compose. The script writes to the folder in `UUDEX_CERTS` (or `-o`), never into this repository. `alice` is a client; `--domain localhost` makes the server certificate (`localhost.crt`, `localhost.key`):

       export UUDEX_CERTS="$HOME/.config/uudex/tls"
       ../infrastructure/certs/generate-certs.sh alice --domain localhost

5. In `.env.compose` set `UUDEX_CERTS_DIR` to that folder, and `UUDEX_PROXY_UID` and `UUDEX_PROXY_GID` to the owner of `localhost.key` (`id -u`, `id -g`). The proxy mounts only `ca.crt`, `localhost.crt` and `localhost.key`, read-only; `ca.key` is never mounted. Add the client to the database as an endpoint; no admin route does that yet.
6. Start and stop. `--wait` makes the command exit non-zero if a service is not healthy within 120 seconds; plain `up -d` exits 0 even when the server crash-loops:

       docker compose --env-file .env.compose up --build -d --wait --wait-timeout 120
       docker compose --env-file .env.compose down

7. Try it. The proxy listens on `127.0.0.1:8443` and refuses any client without a certificate signed by `ca.crt`, at the TLS handshake (no HTTP status). `UUDEX_PROXY_BIND` changes the address; leave it on loopback unless clients must reach the proxy from other machines.

       C="$UUDEX_CERTS"
       curl --cacert $C/ca.crt https://localhost:8443/                  # fails: certificate required
       curl --cacert $C/ca.crt --cert $C/localhost.crt --key $C/localhost.key https://localhost:8443/   # fails: bad certificate
       curl --cacert $C/ca.crt --cert $C/alice.crt --key $C/alice.key https://localhost:8443/endpoint/me   # 200 for a seeded endpoint

The proxy is the only way in: it has one router, and that router adds the verified certificate as `X-Forwarded-Tls-Client-Cert`, replacing anything the client sent. Any router you add to `traefik/dynamic.yml` that reaches the server must carry the `client-cert` middleware, because the server does not verify signatures. Do not mount the Docker socket or enable the Traefik API or dashboard.

The database and the proxy have pinned images, memory limits and healthchecks, and each service waits for the one before it. The server publishes no port. It sits on the `app` network (shared with the proxy) and on the `db` network with PostgreSQL; both are internal. The proxy also sits on `edge`, which is not internal, so Docker can publish port 8443. The server trusts the client-certificate header only from the proxy's fixed address, 172.29.77.20 (`TRUSTED_PROXY_HOSTS`). The `app` network hands out dynamic addresses only from 172.29.77.128/25, so another container cannot take .10 or .20 while the proxy is down. Uvicorn listens only on the server's fixed `app` address (172.29.77.10), so PostgreSQL and any other container on `db` cannot reach it. If that subnet clashes with yours, change it in `compose.yaml` everywhere it appears: the subnet and `ip_range`, the server's `ipv4_address`, the `--host` address in its `command`, its healthcheck URL, `TRUSTED_PROXY_HOSTS`, and the proxy's `ipv4_address`: seven places in all. The host can still reach the server's `app` address, but the trusted-peer check refuses it; keep untrusted users off the host anyway. RabbitMQ is not part of this stack; the `messagebus_connection` example is only a placeholder.

The database password takes effect only when the `db_data` volume is first created. Editing `compose_postgres_password` later does not change the role's password; the old one keeps working. To change it, open `psql` in the running database and use `\password`, which prompts for the new password so it never appears on a command line or in your shell history:

    docker compose --env-file .env.compose exec db psql -U postgres_user -d uudex
    \password postgres_user

Then update both secret files to match (`chmod u+w` them first) and recreate the server. Plain `up -d` keeps the old DSN, so force it:

    docker compose --env-file .env.compose up -d --wait --force-recreate server

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
