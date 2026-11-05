# Certificate helper scripts

Development-only helpers. The certificates they make are examples, not for
real deployment.

- `generate-certs.sh`: makes a local CA, a server certificate and a client
  certificate signed by that CA.
- `generate-certs-from-existing-postgres.sh`: reads the endpoint table in
  PostgreSQL and makes one client certificate per `certificate_dn`, signed by
  the same kind of local CA. It needs `psql` and `openssl`, and a database
  password in `DB_PASSWORD` (there is no default).

## Where files are written

Both scripts write to `~/.config/uudex/tls` by default, never into the
repository. To use another folder, set `UUDEX_CERTS` or pass `-o` / `--output-dir`:

```bash
export UUDEX_CERTS=/custom/cert/path
./generate-certs.sh alice
```

## generate-certs.sh

```bash
./generate-certs.sh                       # client "client", server cert for localhost
./generate-certs.sh alice                 # named client
./generate-certs.sh bob "Acme Corporation"
./generate-certs.sh --server-only "My Organization" --domain localhost --domain api.example.com
./generate-certs.sh alice "My Org" --domain localhost --domain api.local
./generate-certs.sh --list                # list existing certificates
```

| Option | Description |
|--------|-------------|
| `--domain DOMAIN` | Add a domain to the server certificate (repeatable) |
| `--server-only` | Make only the server certificate |
| `--list` | List existing certificates |
| `-c, --country CODE` | Country code |
| `-s, --state STATE` | State or province |
| `-l, --city CITY` | City or locality |
| `-d, --days DAYS` | Validity in days |
| `-k, --key-size SIZE` | RSA key size in bits |
| `-o, --output-dir DIR` | Output folder (overrides `UUDEX_CERTS`) |
| `-h, --help` | Show help |

## generate-certs-from-existing-postgres.sh

```bash
DB_PASSWORD=... ./generate-certs-from-existing-postgres.sh --dry-run
DB_PASSWORD=... ./generate-certs-from-existing-postgres.sh --host db.example --active-only
```

Set the password in the environment; a `--password` value shows in the
process list. Run `--help` for the other options.

## Files written

For each client:

- `{client}.crt`: client certificate (PEM)
- `{client}.key`: client private key (PEM)
- `{client}.p12`: certificate bundle (PKCS#12, for browsers)

The CA:

- `ca.crt`: CA certificate
- `ca.key`: CA private key, keep it secret
- `ca-trusted.crt`: copy of the CA certificate for servers that trust it

The server (`generate-certs.sh` only):

- `localhost.crt`, `localhost.key`: used when the only domain is `localhost`
- `server.crt`, `server.key`: used for several or non-localhost domains, with
  Subject Alternative Names

## Checking a certificate

```bash
openssl verify -CAfile ~/.config/uudex/tls/ca.crt ~/.config/uudex/tls/alice.crt
openssl x509 -in ~/.config/uudex/tls/alice.crt -noout -subject -enddate
curl --cacert ~/.config/uudex/tls/ca.crt \
     --cert ~/.config/uudex/tls/alice.crt --key ~/.config/uudex/tls/alice.key \
     https://localhost:8443/
```
