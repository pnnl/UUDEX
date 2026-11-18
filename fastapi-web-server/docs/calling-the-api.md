# Calling the API with a client certificate

Checked against commit edaf169.

The running stack from [running-the-stack.md](running-the-stack.md) is assumed: the proxy answers on `https://localhost:8443`, the client `alice` has a certificate, and the participant and endpoint rows for `alice` exist (step 7 there). Every request must present a client certificate, and the server takes the caller's identity from it.

Set these once in your shell. `<certs-dir>` is the folder you gave `generate-certs.sh`:

```bash
C=<certs-dir>
api() { curl -sS --cacert $C/ca.crt --cert $C/alice.crt --key $C/alice.key -w '\n-> %{http_code}\n' "$@"; }
```

## Who am I

```bash
api https://localhost:8443/endpoint/me
```

```text
{"active_sw":"Y","endpoint_uuid":"e-alice-0001","certificate_dn":"alice","uudex_administrator_sw":"N","endpoint_id":1,"create_datetime":"2026-11-18T20:32:48.696687Z","endpoint_user_name":"alice","description":"local development client","participant_administrator_sw":"N","participant_id":1}
-> 200
```

The `endpoint_uuid` is the row from the database whose `certificate_dn` equals the certificate's common name.

## List things

These return `200` on a fresh database. The lists are empty until something is created:

```bash
api https://localhost:8443/participants/
api https://localhost:8443/endpoint/
api https://localhost:8443/datasets/
api https://localhost:8443/subjects/
api https://localhost:8443/subscriptions/
```

```text
[{"create_datetime":"2026-11-18T20:32:48.691348Z","participant_short_name":"org","description":null,"participant_id":1,"active_sw":"Y","participant_uuid":"p-0001","participant_long_name":"Organization","root_org_sw":"Y"}]
-> 200
```

(That output is from `/participants/`; the last three print `[]` and `-> 200`.) A missing id gives a 404 with a reason:

```bash
api https://localhost:8443/endpoint/999
```

```text
{"detail":"Endpoint not found"}
-> 404
```

## The API reference

`https://localhost:8443/docs` is Swagger UI, and `https://localhost:8443/openapi.json` is the schema. Both go through the proxy, so a browser needs the client certificate too: import `alice.p12` (its password is printed by `generate-certs.sh`) and the CA certificate `ca.crt`. A browser was not used for this check; the same two paths answer `200` to the `curl` command above.

## What a refused call looks like

The proxy refuses at the TLS handshake, so there is no HTTP status. `curl` ends with an error:

```bash
curl --cacert $C/ca.crt https://localhost:8443/
```

```text
curl: (56) OpenSSL SSL_read: OpenSSL/3.5.4: error:0A00045C:SSL routines::tlsv13 alert certificate required, errno 0
```

The server certificate used as a client gives `ssl/tls alert bad certificate`, and a certificate from another CA is refused at the handshake too (`tests/compose/check-proxy.sh` checks both: see [testing.md](testing.md)).

A certificate that the proxy accepts but whose common name has no endpoint row reaches the server, and the server answers `401`. The example uses a second client, made with `../infrastructure/certs/generate-certs.sh bob` into the same folder and not added to the database:

```bash
curl -sS --cacert $C/ca.crt --cert $C/bob.crt --key $C/bob.key https://localhost:8443/endpoint/me -w '\n-> %{http_code}\n'
```

```text
{"detail":"Unauthorized: Invalid certificate"}
-> 401
```

## Not working yet

On this commit, `/subject/uuid/{subject_uuid}` and `/subject/{subject_uuid}/queue-info` return `500` (both were called for this check). The cause is in pnnl/UUDEX#67: the repository calls a method the async session does not have, and the issue lists reads by id, updates and deletes as affected. A fix is open as pnnl/UUDEX#74. The calls on this page do not touch it.
