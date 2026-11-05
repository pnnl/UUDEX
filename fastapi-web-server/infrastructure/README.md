# Infrastructure

Local-development infrastructure for the UUDEX FastAPI web server. The example passwords and roles in these files are for local development only and are not for real deployment.

## PostgreSQL

See [postgresql/README.md](./postgresql/README.md). Start it with:

```bash
cd postgresql
docker-compose up -d
```

## Certificates

The certificate scripts live in `infrastructure/certs/` at the repository root, not in this directory. By default they write to `~/.config/uudex/tls`, not into the repository. For example:

```bash
./infrastructure/certs/generate-certs.sh --list
```

| Variable | Description | Default |
|----------|-------------|---------|
| `UUDEX_CERTS` | Override certificate output directory | `~/.config/uudex/tls` |

## Requirements

- Docker for the database services
- OpenSSL for certificate generation
