# UUDEX-Server

This server implementation uses FastAPI as its basis for data access. Each guide below says what it was checked against. The code and descriptions were read at commit f5b05cb; the example outputs were last run against a live stack at edaf169.

## Warnings

- The example secrets, passwords and database role in this directory are for local development only. They are not for real deployment.
- The server takes client identity from the `X-Forwarded-Tls-Client-Cert` header, and believes it only from the peers listed in `TRUSTED_PROXY_HOSTS`. Run it only behind a proxy that verifies client certificates and replaces that header. Do not expose it directly.
- Never publish port 8000. Only the verifying proxy may reach the server, over an internal network. A container started without `--network` is reachable from the host and from every other container on the default bridge.
- Any router you add to `traefik/dynamic.yml` that reaches the server must carry the `client-cert` middleware, because the server does not verify signatures. Do not mount the Docker socket or enable the Traefik API or dashboard.
- The proxy listens on `127.0.0.1:8443`. Leave `UUDEX_PROXY_BIND` on loopback unless clients must reach the proxy from other machines.
- Keep Docker access limited to people you trust with the server: anyone who controls Docker can start a container at the proxy's address.
- Never pass a secret as a command-line argument; `ps` shows it. Environment variables are visible to the same user and to root through `/proc/<pid>/environ`; prefer the files in `secrets/`.

## Guides

| I want to | Read |
|-----------|------|
| Run the server on my machine, with a database and a first administrator | [docs/running-locally.md](docs/running-locally.md) |
| Run the full stack: server, PostgreSQL and the proxy, with test certificates | [docs/running-the-stack.md](docs/running-the-stack.md) |
| Call the API as a client with a certificate, and see what a refusal looks like | [docs/calling-the-api.md](docs/calling-the-api.md) |
| Run the tests, the lint and the proxy check script | [docs/testing.md](docs/testing.md) |

## Quickstart

You need Docker with Compose, `openssl` and `curl`. From this directory (full steps, with the output to expect, in [docs/running-the-stack.md](docs/running-the-stack.md)):

```bash
export UUDEX_CERTS=<certs-dir>        # folder for the certificates; you choose it
export CLIENT=alice                   # your client common name (CN)
export BASE=https://localhost:8443    # change for a different host or port
[ -e .env.compose ] || cp .env.compose.example .env.compose
for n in postgres_password postgres_dsn messagebus_connection x_ssl_cert; do
  [ -e secrets/compose_$n ] || cp secrets/example.compose_$n secrets/compose_$n
done
chmod 0444 secrets/compose_* && chmod 0700 secrets
../infrastructure/certs/generate-certs.sh $CLIENT --domain localhost
# in .env.compose: set UUDEX_CERTS_DIR to $UUDEX_CERTS, UUDEX_PROXY_UID and UUDEX_PROXY_GID to `id -u` and `id -g`
docker compose --env-file .env.compose up --build -d --wait --wait-timeout 120
```

Then add the client `$CLIENT` to the database (step 8) and call the API:

```bash
curl --cacert $UUDEX_CERTS/ca.crt --cert $UUDEX_CERTS/$CLIENT.crt --key $UUDEX_CERTS/$CLIENT.key $BASE/endpoint/me
```

Stop with `docker compose --env-file .env.compose down`.

## Where things are

- Swagger UI: `https://localhost:8443/docs`, through the proxy. The proxy refuses a client that has no certificate from the CA, so the browser needs the client certificate and the CA installed first ([docs/calling-the-api.md](docs/calling-the-api.md)).
- Settings: environment variables, then a `.env` file, then the files in `secrets/`, then defaults. See [docs/running-locally.md](docs/running-locally.md). The tests read `tests/.env.test` only.
- Container image: [docs/running-the-stack.md](docs/running-the-stack.md), "Running the image alone".
- First administrator (`uudex-server bootstrap-admin`): [docs/running-locally.md](docs/running-locally.md); in the stack, [docs/running-the-stack.md](docs/running-the-stack.md).
- Database password changes and how the stack is wired (networks, fixed addresses, TLS settings): [docs/running-the-stack.md](docs/running-the-stack.md).
- PostgreSQL for local work: [docs/running-locally.md](docs/running-locally.md), step 3. A separate setup with RabbitMQ is described in [infrastructure/postgresql/README.md](infrastructure/postgresql/README.md).
- The proxy check script (`tests/compose/check-proxy.sh`): [docs/testing.md](docs/testing.md).

## Generating the client

These steps were not re-checked against edaf169. The `generated-client-api` directory they name is not in this tree.

1. Make sure you have activated the server code.
2. cd to the 'generated-client-api' directory.
3. Execute 'openapi-python-client update --path openapi.json'

## Updating the openapi.json file

1. Open a browser to the Swagger UI (<https://localhost:8443/docs>).
2. Click on </openapi.json> under the title of UUDEX API.
