# Running the server locally

Checked against commit edaf169.

This page starts the server on your machine with `uvicorn`, without the proxy. Use it to work on the code. To test with client certificates, use [running-the-stack.md](running-the-stack.md) instead.

The server believes the client identity in the `X-Forwarded-Tls-Client-Cert` header from any peer listed in `TRUSTED_PROXY_HOSTS`. Run without the proxy, only `/docs` and `/openapi.json` answer; every other path returns 401. Do not expose this process to a network.

You need Python 3.11 or newer, [Poetry](https://python-poetry.org/) (CI uses 2.2.1), and Docker for the database. Run every command from the `fastapi-web-server` directory.

## 1. Install

```bash
poetry install --with dev --no-interaction
```

The `uudex-server` command and `uvicorn` are then available through `poetry run`.

## 2. Settings

Settings come from, in order of priority: environment variables, a `.env` file (if present), the files in `secrets/`, then defaults.

1. Copy `.env.example` to `.env`. It already holds a placeholder `X_SSL_CERT`, which is enough for local work.
2. Copy `secrets/example.postgres_dsn` to `secrets/postgres_dsn` and `secrets/example.messagebus_connection` to `secrets/messagebus_connection`, one value per file, and edit them. This is the recommended way. The database URL must use the async driver (`postgresql+asyncpg://`).
3. Environment variables are allowed, but are visible to the same user and to root through `/proc/<pid>/environ`.
4. Never pass a secret as a command-line argument; `ps` shows it.

```bash
cp .env.example .env
cp secrets/example.postgres_dsn secrets/postgres_dsn
cp secrets/example.messagebus_connection secrets/messagebus_connection
```

`UUDEX_SETTINGS` and `UUDEX_SECRETS_DIR` name another env file or secrets directory. A name that does not exist stops startup with an error. Relative paths are relative to this directory. The `.env` and `secrets/` copies are ignored by git. The example values are for local development only.

The tests do not read these files; they read `tests/.env.test` only.

## 3. Database

The server needs PostgreSQL. It creates its tables itself on startup. SQLite is for the tests only.

This starts one throwaway PostgreSQL container, bound to loopback on port 55432 so it does not clash with a PostgreSQL already on 5432. The password is read from a file, so it never appears on a command line. `<pw-file>` is a file you create that holds only the password.

```bash
docker run -d --name uudex-localdb --memory 512m \
  -p 127.0.0.1:55432:5432 \
  -e POSTGRES_USER=postgres_user -e POSTGRES_DB=uudex \
  -e POSTGRES_PASSWORD_FILE=/run/pw -v <pw-file>:/run/pw:ro \
  postgres:18.1-alpine3.22@sha256:270579ee277a572fa8cfdbaec0e1ff588bb7247da92d25165c7237c483e565d9
```

Put the same password in `secrets/postgres_dsn`:

```text
postgresql+asyncpg://postgres_user:<password>@localhost:55432/uudex
```

Remove it when you are done: `docker rm -f uudex-localdb`. The data goes with it.

The image is the one `compose.yaml` pins. `infrastructure/postgresql/README.md` describes a different setup (PostgreSQL 14.1 with RabbitMQ and fixed development credentials, data under your home directory). It was not part of this check.

## 4. Start the server

```bash
poetry run uvicorn uudex_server.main:app --host 127.0.0.1 --port 8100 --no-proxy-headers
```

Port 8000 is the default; the example uses 8100 in case something else holds it. Keep `--no-proxy-headers`, so a client cannot replace the peer address the trust check reads. Expected output ends with:

```text
trusted_proxy_hosts is empty: no peer is trusted, so every non-public request will be refused. ...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8100 (Press CTRL+C to quit)
```

The warning is expected here. From another terminal:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8100/openapi.json   # 200
curl -s -w '\n%{http_code}\n' http://127.0.0.1:8100/                          # "Request not from a trusted proxy." 401
```

`/docs` (Swagger UI) opens in a browser at `http://127.0.0.1:8100/docs`. To call the other routes you need the proxy and a client certificate: see [calling-the-api.md](calling-the-api.md).

Stop the server with Ctrl+C.

## 5. First administrator

No API call creates the first administrator. The command below needs an existing participant, so insert one with `psql` first. This uses the container from step 3:

```bash
docker exec -i uudex-localdb psql -U postgres_user -d uudex <<'SQL'
insert into participant (active_sw, participant_uuid, participant_short_name, participant_long_name, root_org_sw)
  values ('Y', 'p-0001', 'org', 'Organization', 'Y');
select participant_id, participant_uuid from participant;
SQL
```

The select prints `participant_id` 1. Then run, with the participant id from that output:

```bash
poetry run uudex-server bootstrap-admin --cn <name> --participant-id 1
```

`<name>` is the common name of the administrator's client certificate. The command prints the new endpoint's uuid and exits 0:

```text
uudex-server: Loading settings from: <path>/.env
uudex-server: database: postgresql+asyncpg://postgres_user:***@localhost:55432/uudex
c60d19cd-e9e7-47a7-a254-f2ed881c0d99
```

It exits 1, writes nothing and says why on stderr when an active administrator already exists, the participant is missing or inactive, an endpoint already has that certificate DN, or the name is one the server would refuse (empty, edge whitespace, control characters). A second run gives:

```text
uudex-server: refused: an active administrator already exists
```

It reads the same settings as the server and prints no secret. Each run prints the settings file and the database it uses to stderr (password hidden). Check the database line: an environment variable or the secrets directory can override the file. Any other failure prints one fixed line naming what failed (settings, connecting, reading the tables or writing) and never the error text. Only a failure before the write says "nothing was written"; after it, look for an endpoint with that certificate DN before running again. Two runs started together are safe: the second is refused. The PostgreSQL guard for that was checked by hand and no test runs it yet (#39).

For the compose stack the same command runs inside the server container: see [running-the-stack.md](running-the-stack.md).
