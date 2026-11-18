# Running the tests

Checked against commit edaf169.

Run every command from the `fastapi-web-server` directory. CI (`../.github/workflows/ci.yml`, one level up from that directory) runs two jobs on Python 3.13, `lint` and `test`. This page runs the same commands. Use a virtual environment for the `pip install` lines.

## The test suite

```bash
pip install poetry==2.2.1
poetry install --with dev --no-interaction
poetry run pytest -v -rA
```

The tests read `tests/.env.test` only (placeholder values, a SQLite database). They need no PostgreSQL, no Docker, no secrets and no certificates, and they ignore your `.env` and `secrets/`. The install took about 11 seconds and the run about a minute. The last line was:

```text
=========== 337 passed, 113 xfailed, 20 warnings in 63.66s (0:01:03) ===========
```

An `xfail` is a test for a known gap, marked with the issue that tracks it (for example `#16` or `#17` in the `-rA` summary). `pytest.ini` sets `xfail_strict`, so when a fix makes one pass, the run fails until the mark is removed. A count other than the one above does not mean a problem by itself: the numbers change as the issues close.

Run part of the suite by file or by name:

```bash
poetry run pytest tests/test_settings.py -q          # 20 passed
poetry run pytest -k trusted_proxy -q                # 64 passed
```

The suite includes `tests/test_compose_proxy.py`, which reads `compose.yaml` and the files in `traefik/` and checks the stack's safety rules (the fixed addresses agree, the proxy mounts only three certificate files, and so on). It does not start Docker.

## Lint

CI pins ruff 0.1.15 because the poetry lock pulls a newer one; the pin matches `.pre-commit-config.yaml`:

```bash
pip install ruff==0.1.15
ruff check src tests
ruff format --check src tests
```

Both exit 0 on this commit. `ruff check` prints nothing when it finds nothing; the format check ends with `79 files already formatted`.

## The proxy check script

`tests/compose/check-proxy.sh` checks a running stack. It does not start, stop or seed anything and never writes to the database. Start and seed the stack first: [running-the-stack.md](running-the-stack.md), steps 1 to 7.

```bash
tests/compose/check-proxy.sh <certs-dir> uudex alice
```

The arguments are the certificates folder, the compose project name (`uudex` unless you used `-p`) and the client name (default `alice`). It prints one `PASS` or `FAIL` line per check and ends with `all checks passed` (about 3 seconds):

```text
PASS valid client gets 200 with its endpoint on /endpoint/me
PASS forged forwarded certificate and subject header still give the valid client
PASS ca.crt holds exactly one certificate, on the host and inside the proxy
...
PASS proxy command is [traefik]
PASS proxy has no tmpfs
all checks passed
```

It exits non-zero if any check fails: 1 for a failed check, 2 when it cannot run. A project with no running proxy gives `error: no running proxy container for project <name>` and exit 2; no arguments gives a usage line and exit 2.

It compares the running proxy with the commit at `HEAD`: the pinned image, its own entrypoint, command and environment, that it has no tmpfs, the mounts, and both `traefik/` files byte for byte, on the host and as the proxy reads them. So it needs the Traefik files committed and unmodified, and the proxy must be running exactly those bytes: it fails when any of the proxy's five files changed after the proxy started, even a restore. After changing any of them (both `traefik/` files, `ca.crt`, `localhost.crt`, `localhost.key`), recreate the proxy (`docker compose --env-file .env.compose up -d --force-recreate proxy`). `ca.crt` must hold exactly one certificate, on the host and in the proxy.

What it does not see: a clock set back (by hand, or by NTP further than the time between the proxy's start and the change), a file system where replacing a file does not move its change time, a write from inside the container, or a change made and undone before the proxy started. A Docker socket forwarded from another host passes the local-daemon check. It must run on the Docker host (a remote Docker context is refused) from this checkout. It cannot protect against someone with Docker access acting on purpose; keep that access limited.

A signal (HUP, INT, QUIT, TERM) to the whole process group stops it at once with exit 129, 130, 131 or 143; sent to the script alone it stops after the running call, at most 65 seconds; KILL leaves its temporary folder, which holds no real key.

The script needs `curl`, `openssl`, `docker` and `git`, and GNU coreutils.
