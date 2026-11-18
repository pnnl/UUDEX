# Running the stack with the proxy

Checked against commit edaf169.

`compose.yaml` starts the server, PostgreSQL and a Traefik proxy that verifies client certificates. The values in the example files are for local development only. They are not for real deployment.

The proxy is the only way in: it has one router, and that router adds the verified certificate as `X-Forwarded-Tls-Client-Cert`, replacing anything the client sent. The server publishes no port. Do not expose it directly, and do not mount the Docker socket or enable the Traefik API or dashboard.

You need Docker with Compose, `openssl` and `curl`. About 1.3 GB of memory is reserved by the limits in `compose.yaml` (512 MB for the server, 512 MB for PostgreSQL, 256 MB for the proxy). Run every command from the `fastapi-web-server` directory. The first start builds the server image and pulls two others.

## 1. Copy the examples

Each secret is one file, mounted under `/run/secrets`; none goes in `environment:` or on a command line. Existing copies are kept, so it is safe to run this again:

```bash
[ -e .env.compose ] || cp .env.compose.example .env.compose
for n in postgres_password postgres_dsn messagebus_connection x_ssl_cert; do
  [ -e secrets/compose_$n ] || cp secrets/example.compose_$n secrets/compose_$n
done
```

## 2. Passwords

The password in `compose_postgres_password` and the one inside `compose_postgres_dsn` must match; the DSN host is `db`. The examples already match (`dev-only-change-me`), so you can leave them for a first run. Change both together if you edit one.

## 3. Lock the files

They must be readable by uid 10001 (the server) and root (PostgreSQL). Compose cannot set file secret owners, so mode 0444 inside a 0700 directory keeps other host users out. To edit a file later, `chmod u+w` it first.

```bash
chmod 0444 secrets/compose_*
chmod 0700 secrets
```

## 4. Make the certificates

Run this as the user who will run compose. The script writes to the folder in `UUDEX_CERTS` (or `-o`), never into this repository. `alice` is a client; `--domain localhost` makes the server certificate (`localhost.crt`, `localhost.key`). The folder `<certs-dir>` is one you choose; the script makes it with mode 700 and refuses one that other users can write.

```bash
export UUDEX_CERTS=<certs-dir>
../infrastructure/certs/generate-certs.sh alice --domain localhost
```

It prints the paths it wrote and ends with a `curl` example. That example omits the port; this stack listens on 8443. The client bundle `alice.p12` (for a browser) has the password `changeme`. More options: `../infrastructure/certs/README.md`.

## 5. Tell compose where they are

In `.env.compose` set `UUDEX_CERTS_DIR` to that folder, and `UUDEX_PROXY_UID` and `UUDEX_PROXY_GID` to the owner of `localhost.key` (`id -u`, `id -g`). The proxy mounts only `ca.crt`, `localhost.crt` and `localhost.key`, read-only; `ca.key` is never mounted. The example file leaves the two ids empty on purpose: compose refuses to start until you fill them in.

## 6. Start

```bash
docker compose --env-file .env.compose up --build -d --wait --wait-timeout 120
```

`--wait` makes the command exit non-zero if a service is not healthy within 120 seconds; plain `up -d` exits 0 even when the server crash-loops. The output ends with the three containers `Healthy`:

```text
 Container uudex-db-1  Healthy
 Container uudex-server-1  Healthy
 Container uudex-proxy-1  Healthy
```

"Healthy" is a weak signal. For the proxy it means only that the process answers its ping. For the server it means only that it answers HTTP on `/openapi.json`; it does not show that the database is reachable or usable. A proxy that cannot read its key, or that failed to load `traefik/dynamic.yml`, can still report healthy while it refuses every client. So run the checks in step 8.

`compose.yaml` names the project `uudex`. To use another project name, add `-p <name>` to every compose command, and pass the same name to the check script. The proxy publishes port 8443 on the host, so only one stack can run at a time.

## 7. Add the client to the database

Identity comes from the certificate, but the server also needs an endpoint row for it, and no admin route creates one yet. Insert a participant and an endpoint whose `certificate_dn` is the certificate's common name:

```bash
docker compose --env-file .env.compose exec -T db psql -U postgres_user -d uudex <<'SQL'
insert into participant (active_sw, participant_uuid, participant_short_name, participant_long_name, root_org_sw)
  values ('Y', 'p-0001', 'org', 'Organization', 'Y');
insert into endpoint (active_sw, endpoint_uuid, endpoint_user_name, certificate_dn, description,
    uudex_administrator_sw, participant_administrator_sw, participant_id)
  select 'Y', 'e-alice-0001', 'alice', 'alice', 'local development client', 'N', 'N', participant_id
  from participant where participant_uuid = 'p-0001';
SQL
```

Each insert prints `INSERT 0 1`. Leave out `-T` and the heredoc to get an interactive `psql` instead.

## 8. Check it

The proxy listens on `127.0.0.1:8443`. `UUDEX_PROXY_BIND` changes the address; leave it on loopback unless clients must reach the proxy from other machines. Run the first check before the others: it shows that a valid client gets through on this port, so a failure in the next two means the certificate was refused and not that the stack is down or the port is wrong. The proxy refuses at the TLS handshake, so there is no HTTP status for the refused ones; each ends with the error shown.

```bash
C=<certs-dir>
curl --cacert $C/ca.crt --cert $C/alice.crt --key $C/alice.key https://localhost:8443/endpoint/me   # 200, with e-alice-0001 in the body
curl --cacert $C/ca.crt https://localhost:8443/                  # fails: "tlsv13 alert certificate required"
curl --cacert $C/ca.crt --cert $C/localhost.crt --key $C/localhost.key https://localhost:8443/   # fails: "ssl/tls alert bad certificate"
```

For the full set of proxy checks, run `tests/compose/check-proxy.sh`: see [testing.md](testing.md).

## Stop

```bash
docker compose --env-file .env.compose down
```

This removes the containers and networks and keeps the database volume, so the rows from step 7 are still there the next time you start. To delete the database as well and start clean, add `-v`. Add `--rmi local` to also remove the image compose built.

## Add the first administrator

The same command as in [running-locally.md](running-locally.md), run inside the server container (the image installs the `uudex-server` command). The participant from step 7 must exist; use its `participant_id` (1 on a fresh database).

```bash
docker compose --env-file .env.compose exec server uudex-server bootstrap-admin --cn <name> --participant-id <id>
```

Output, for a first run and for a second:

```text
uudex-server: Loading settings from: environment
uudex-server: database: postgresql+asyncpg://postgres_user:***@db:5432/uudex
03878f3d-0ffb-429b-a880-2e2845e16f15
```

```text
uudex-server: refused: an active administrator already exists
```

The exit codes, the refusals and the failure messages are described in [running-locally.md](running-locally.md). Add `-T` when the command is not run from a terminal.

## Change the database password

The database password takes effect only when the `db_data` volume is first created. Editing `compose_postgres_password` later does not change the role's password; the old one keeps working. To change it, open `psql` in the running database and use `\password`, which prompts for the new password so it never appears on a command line or in your shell history:

```bash
docker compose --env-file .env.compose exec db psql -U postgres_user -d uudex
```

At the `psql` prompt:

```text
\password postgres_user
```

Then update both secret files to match (`chmod u+w` them first) and recreate the server. Plain `up -d` keeps the old DSN, so force it:

```bash
docker compose --env-file .env.compose up -d --wait --force-recreate server
```

Or run `docker compose --env-file .env.compose down -v`, which deletes the database and starts clean. Do not leave a real password in your shell history.

## Running the image alone

Build, from this directory:

```bash
docker build -t uudex-server .
```

Create an internal network shared only with the verifying proxy, then run the server on it. Give it a database it can reach on that network (the DSN in the secrets directory names the database container). Add `-d` to keep your terminal:

```bash
docker network create --internal uudex-internal
docker run --rm --network uudex-internal --read-only --tmpfs /tmp --memory 512m \
  -e X_SSL_CERT=... -v <secrets-dir>:/run/secrets:ro uudex-server
```

The secrets are mounted read-only at `/run/secrets` (the image sets `UUDEX_SECRETS_DIR` to it). The default Docker bridge is not safe: a server started without `--network` is reachable from the host and from every other container on that bridge. Put the proxy and the database on the internal network too, since it has no outside access. The host itself can still reach the container's address on that network, so keep untrusted users off the host.

- Each secret file (`postgres_dsn`, `messagebus_connection`) must be readable by uid 10001; owner 10001 and mode 0400 is recommended. If you are not that user, mode 0444 on the files and 0755 on the folder also works; keep that to a development machine.
- Use absolute paths for any setting you give the container. Relative paths resolve inside the virtualenv there, not in this directory.
- SQLite is for tests only; the image has no SQLite driver and will not start with it.
- Never publish port 8000. Only the verifying proxy may reach it, over an internal network. The image listens on all addresses, so on a network shared with other containers, pass `--host <one address>` to uvicorn as `compose.yaml` does.

A start that works ends with `Application startup complete.` and `Uvicorn running on http://0.0.0.0:8000`. The `trusted_proxy_hosts is empty` warning appears too, because nothing trusts a peer until you set `TRUSTED_PROXY_HOSTS`. Remove the network with `docker network rm uudex-internal` when you are done.

## How the stack is wired

The proxy accepts TLS 1.2 and 1.3. TLS 1.2 is limited to ECDHE with AES-GCM or ChaCha20, so older CBC and SHA-1 suites are refused. It logs one line per request on stdout (`docker compose --env-file .env.compose logs proxy`); request headers, including the forwarded certificate, are not logged.

Any router you add to `traefik/dynamic.yml` that reaches the server must carry the `client-cert` middleware, because the server does not verify signatures.

The database and the proxy have pinned images, memory limits and healthchecks, and each service waits for the one before it. The server publishes no port. It sits on the `app` network (shared with the proxy) and on the `db` network with PostgreSQL; both are internal. The proxy also sits on `edge`, which is not internal, so Docker can publish port 8443. The server trusts the client-certificate header only from the proxy's fixed address, 172.29.77.20 (`TRUSTED_PROXY_HOSTS`). The `app` network hands out dynamic addresses only from 172.29.77.128/25, so Docker gives neither .10 nor .20 to another container on its own. Anyone who controls Docker can still start a container at .20, so keep Docker access limited to people you trust with the server. Uvicorn listens only on the server's fixed `app` address (172.29.77.10), so PostgreSQL and any other container on `db` cannot reach it. If that subnet clashes with yours, change it in `compose.yaml` everywhere it appears: the subnet and `ip_range`, the server's `ipv4_address`, the `--host` address in its `command`, its healthcheck URL, `TRUSTED_PROXY_HOSTS`, and the proxy's `ipv4_address`. `tests/test_compose_proxy.py` checks that these agree. The commented `TRUSTED_PROXY_HOSTS` example in `.env.example` is illustrative and is not read by compose. The host can still reach the server's `app` address, but the trusted-peer check refuses it; keep untrusted users off the host anyway. RabbitMQ is not part of this stack; the `messagebus_connection` example is only a placeholder.
