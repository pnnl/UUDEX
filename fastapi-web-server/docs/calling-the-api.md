# Calling the API with a client certificate

Checked against: The code and descriptions were read at commit f5b05cb; the example outputs were last run against a live stack at edaf169.

The running stack from [running-the-stack.md](running-the-stack.md) is assumed: the proxy answers on `$BASE`, your client has a certificate, and the participant and endpoint rows for it exist (step 8 there). Every request must present a client certificate, and the server takes the caller's identity from it.

Run the same exports as step 1 of [running-the-stack.md](running-the-stack.md), and put in your own client common name (CN) and participant. The values shown are the examples used in the outputs on this page, and `running-the-stack.md` uses the same names. `UUDEX_CERTS` is the folder you gave `generate-certs.sh`. Change `BASE` if the proxy is on another host or port:

```bash
export UUDEX_CERTS=<certs-dir>        # folder for the certificates; you choose it
export CLIENT=alice                   # your client common name (CN)
export BASE=https://localhost:8443    # change for a different host or port
export PARTICIPANT_UUID=p-0001
export PARTICIPANT_SHORT=org
export PARTICIPANT_LONG=Organization
export ENDPOINT_UUID=e-alice-0001
api() { curl -sS --cacert $UUDEX_CERTS/ca.crt --cert $UUDEX_CERTS/$CLIENT.crt --key $UUDEX_CERTS/$CLIENT.key -w '\n-> %{http_code}\n' "$@"; }
```

Every call below needs a certificate whose CN has an active endpoint row. Without one the answer is `401`, see the end of this page.

## Who am I

`/endpoint/me` shows which endpoint the server thinks your certificate is: your endpoint row, with its participant, your administrator flags and whether it is active. Call it first to check that the certificate, the proxy and the database row agree. Any caller may use it; it returns only the caller's own row.

```bash
api $BASE/endpoint/me
```

```text
{"active_sw":"Y","endpoint_uuid":"e-alice-0001","certificate_dn":"alice","uudex_administrator_sw":"N","endpoint_id":1,"create_datetime":"2026-11-18T20:32:48.696687Z","endpoint_user_name":"alice","description":"local development client","participant_administrator_sw":"N","participant_id":1}
-> 200
```

The `endpoint_uuid` is the row from the database whose `certificate_dn` equals the certificate's common name.

## List things

These return `200` on a fresh database. The lists are empty until something is created. What each one gives you, from the route code:

| Call | What it returns | Who sees what |
|---|---|---|
| `/participants/` | Every participant (organization) in the exchange. Use it to find a `participant_id`. | Any caller sees all of them. Creating one is a `POST` for administrators only. |
| `/endpoint/` | The endpoints (client identities). Use it to see who else is registered. | An administrator sees all; anyone else sees only the endpoints of their own participant. |
| `/datasets/` | Metadata of datasets (name, size, hash, subject), without the payload. | Only datasets owned by your participant, for everyone, administrators included. |
| `/subjects/` | The subjects (topics) that datasets and subscriptions attach to. | An administrator sees all; anyone else sees only subjects their participant owns. |
| `/subscriptions/` | The subscriptions you own. `/subscriptions/admin` lists everyone's. | Your own endpoint's only; `/subscriptions/admin` is administrators only. |

```bash
api $BASE/participants/
api $BASE/endpoint/
api $BASE/datasets/
api $BASE/subjects/
api $BASE/subscriptions/
```

```text
[{"create_datetime":"2026-11-18T20:32:48.691348Z","participant_short_name":"org","description":null,"participant_id":1,"active_sw":"Y","participant_uuid":"p-0001","participant_long_name":"Organization","root_org_sw":"Y"}]
-> 200
```

(That output is from `/participants/`; your own is the row whose `participant_uuid` is `$PARTICIPANT_UUID`. `/endpoint/` shows the one endpoint from step 8, and the last three print `[]` and `-> 200`.)

`/endpoint/{endpoint_id}` returns one endpoint by its numeric id, so you can look up a single row. You may read your own participant's endpoints; an administrator may read any. A missing id gives a 404 with a reason, and an id from another participant gives a 403 with this body (taken from the route code, `src/uudex_server/routes/uudex_routes.py:81`; not from a live run):

```bash
api $BASE/endpoint/999
```

```text
{"detail":"Endpoint not found"}
-> 404
```

```text
{"detail":"Not authorized to view this endpoint"}
-> 403
```

Likewise `/subject/{subject_id}` and `/subject/uuid/{subject_uuid}` return one subject (your participant's, or any for an administrator; `403` otherwise, `404` when missing), and `/subject/{subject_uuid}/queue-info` reports the state of the subject's message queues on the broker (it also gives `409` when the stored broker name is untrusted: `subject_routes.py:725`, `status_code=status.HTTP_409_CONFLICT, detail="Subject broker name needs repair"`). The stack has no RabbitMQ, so the queue call has nothing to talk to there.

## The API reference

`$BASE/docs` is Swagger UI, and `$BASE/openapi.json` is the schema: they list every route, including the ones this page does not call. Both go through the proxy, so a browser needs the client certificate too: import `$CLIENT.p12` (its password is printed by `generate-certs.sh`) and the CA certificate `ca.crt`. A browser was not used for this check; the same two paths answer `200` to the `curl` command above.

## What a refused call looks like

The proxy refuses at the TLS handshake, so there is no HTTP status. `curl` ends with an error:

```bash
curl --cacert $UUDEX_CERTS/ca.crt $BASE/
```

```text
curl: (56) OpenSSL SSL_read: OpenSSL/3.5.4: error:0A00045C:SSL routines::tlsv13 alert certificate required, errno 0
```

The server certificate used as a client gives `ssl/tls alert bad certificate`, and a certificate from another CA is refused at the handshake too (`tests/compose/check-proxy.sh` checks both: see [testing.md](testing.md)).

A certificate that the proxy accepts but whose common name has no endpoint row reaches the server, and the server answers `401`. The example uses a second client, made with `../infrastructure/certs/generate-certs.sh bob` into the same folder and not added to the database:

```bash
curl -sS --cacert $UUDEX_CERTS/ca.crt --cert $UUDEX_CERTS/bob.crt --key $UUDEX_CERTS/bob.key $BASE/endpoint/me -w '\n-> %{http_code}\n'
```

```text
{"detail":"Unauthorized: Invalid certificate"}
-> 401
```

## Known limits

* Everything above is read-only. Writes (`POST` for datasets, subjects, subscriptions, participants and endpoints, and the `PUT` and `DELETE` on subjects) exist; see `$BASE/docs` for their bodies. Participants and endpoints can be created only by an administrator, and the very first administrator comes from `uudex-server bootstrap-admin`, not from the API (see [running-the-stack.md](running-the-stack.md)).
* The subject-by-uuid and queue-info calls returned `500` at edaf169 because the repository called a method the async session does not have (pnnl/UUDEX#67). That fix, pnnl/UUDEX#74, is merged and the repository code now reads rows through `select_by_field`. These two calls were not re-run against a live stack at f5b05cb. The queue-info call also needs a message broker, which the compose stack does not include.
