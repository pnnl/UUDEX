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
repository. The folder is created
with mode 700, and a folder that other users can write is refused. To use another folder, set `UUDEX_CERTS` or pass `-o` / `--output-dir`:

```bash
export UUDEX_CERTS=/custom/cert/path
./generate-certs.sh alice
```

## Config file

`generate-certs.sh` reads your own defaults from a config file, so a run needs
only a client name. Start from the example:

```bash
mkdir -p ~/.config/uudex
cp uudex-certs.conf.example ~/.config/uudex/certs.conf
chmod 600 ~/.config/uudex/certs.conf
```

The script reads `~/.config/uudex/certs.conf` if it exists. To use another
file, pass `--config FILE` or set `UUDEX_CERTS_CONF`; a file named that way
must exist, and `--config` wins over the variable. An empty `UUDEX_CERTS_CONF`
is refused, not read as unset. Keep the file outside the repository.

Format: `KEY = VALUE`, one per line; `#` starts a comment on its own line.
Keys: `C`, `ST`, `L`, `O`, `CA_CN`, `KEY_SIZE`, `DAYS`, `DOMAINS` (comma
separated), `OUTPUT_DIR` (absolute, or starting with `~/`). The file is parsed,
never run. An unknown key, a malformed or repeated line, a bad number, a value
that is blank or starts with `-`, or a file other users can write is refused
with a message naming the file and line, before anything is written.

Subject values (`C`, `ST`, `L`, `O`, `CA_CN`, and the matching options, the
`ORG` argument and the client name) may not contain `/`, `\`, `#`, `$`, `"`,
`'` or `+`, or a control character, because openssl reads them as syntax and
the CA, server and client subjects would differ. They also may not start or
end with a space or tab, which the server request would drop, or contain a
non-ASCII character, which openssl would store double-encoded; use ASCII only.
`L = Richland # city` is refused, not stored. Server names (`DOMAINS` and
`--domain`) must be DNS names (letters, digits, `.`, `-`, `_`, `*`), IPv4
addresses (0 to 255, no leading zeros) or IPv6 addresses (written with `:`, no
dotted tail); an IP address becomes an IP entry in the certificate, not a DNS
name. A DNS name has no empty label (so no leading, trailing or doubled dot),
no label over 63 characters or starting or ending with `-`, and `*` only as
the whole first label (`*.example.com`). A name made only of digits and dots
must be a valid IPv4 address. The first name becomes the certificate common
name, so it may be at most 64 characters.

Precedence: command line, then config file, then built-in default. For the
output folder it is `-o`, then `UUDEX_CERTS`, then `OUTPUT_DIR`, then
`~/.config/uudex/tls`. `--domain` on the command line replaces `DOMAINS`
rather than adding to it. Nothing is required: the client name defaults to
`client`.

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
| `--force` | Replace existing client, server and `ca-trusted.crt` files (never the CA) |
| `--list` | List existing certificates |
| `-c, --country CODE` | Country code |
| `-s, --state STATE` | State or province |
| `-l, --city CITY` | City or locality |
| `-d, --days DAYS` | Validity in days, a whole number from 1 to 999999 |
| `-k, --key-size SIZE` | RSA key size in bits, a whole number from 2048 to 16384 |
| `--org ORG` | Organization (same as the second argument) |
| `--ca-name NAME` | CA common name |
| `--config FILE` | Config file to read (overrides `UUDEX_CERTS_CONF`) |
| `-o, --output-dir DIR` | Output folder (overrides `UUDEX_CERTS`) |
| `-h, --help` | Show help |

An existing CA is kept as it is. If the requested CA subject differs from it,
the script prints a warning on stderr naming both subjects, and the summary
shows the CA subject read from `ca.crt`. Replacing the CA is not supported yet.

Every option that takes a value needs a value that is not blank and does not
start with `-`. `--key-size` and `--days` accept ASCII digits only. The script
checks all arguments before it writes any file, stops at the first failure
with a message naming the step, and exits non-zero. `--list` on a folder that
does not exist prints the reason to stderr and exits 1.

### What is refused

The script checks all of this before it makes any key, and a refused run
changes nothing. Each message names the file or folder.

- A client that already has `<name>.key`, `.crt` or `.p12`, and a
  `ca-trusted.crt` that is not a copy of `ca.crt`. `--force` replaces them: the
  new files are built beside the old ones and renamed over them. If the move
  fails part-way, or is cut off by Ctrl-C, `kill` or a closed terminal (INT,
  TERM, HUP), the files already moved are put back or, if this run made them,
  removed, and the message names them, so the folder is as it was. If a file
  cannot be put back, the `.staging.*` folder is kept, and the message names it
  and the old files in its `.old` folder. Only a `kill -9` during the move can
  leave a mixed set, and then the `.staging.*` folder holds the old files.
- Only one of `ca.key` and `ca.crt`, or a certificate with no CA. Restore the
  CA or empty the folder; `--force` does not apply. A complete CA is reused and
  never replaced.
- A server key without its certificate, or the reverse (without `--force`). A
  complete server certificate is reused, so a second client does not replace it;
  use `--force` to make one for new `--domain` values. A reused key must match
  its certificate. `--server-only` with names that differ from the existing
  certificate is refused; a client run warns, and both summaries list the
  names the certificate really has.
- A reused `ca.key` or server key that the group or others can read or change.
  Run `chmod 600` on it.
- A symbolic link, a directory, a pipe or a file owned by someone else in the
  output folder. The output folder itself may not be a link. A link in a parent
  is followed and the real parents are checked.
- A non-empty folder without the `.uudex-certs` marker, which the script writes
  when it makes a folder. An empty folder you made yourself is accepted and
  marked. A folder made by an older version of this script, or by the postgres
  script, has no marker either: check its CA and certificates, then create an
  empty file named `.uudex-certs` in it. Do not make a new CA beside them.
- A `.staging.*` folder, left by a run that was killed (or one still going).
  First move the files in its `.old` folder back into the output folder, check
  that each key matches its certificate, then delete the staging folder with
  `rm -r`.
- Any parent of the output folder, up to `/`, that the group or others can write
  (sticky or not) or that is owned by neither you nor root. `/tmp/certs` is
  refused for this reason.
- A client named `ca`, `ca-trusted`, `server` or `localhost`.

## generate-certs-from-existing-postgres.sh

```bash
read -rs DB_PASSWORD; export DB_PASSWORD
./generate-certs-from-existing-postgres.sh --dry-run
./generate-certs-from-existing-postgres.sh --host db.example --active-only
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
- `ca.srl`: certificate serial counter
- `.uudex-certs`: marker that this script made the folder

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

## Tests

Run `bats infrastructure/certs/tests/certs.bats` from the repository root (needs `bats` and `openssl`). The tests make `.uudex-certs-bats.*` folders under `$HOME` and remove them afterwards.
