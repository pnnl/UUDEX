#!/usr/bin/env bash
# Checks that the compose stack's proxy is the only way in and verifies client certificates.
# Run it against a stack already started and seeded as described in README, "Compose".
# It does not start, stop or seed anything and never writes to the database.
#
# Usage: check-proxy.sh <certs-dir> <compose-project> [client-cn]
#   certs-dir        folder from generate-certs.sh (ca.crt, <client>.crt, <client>.key, localhost.crt/.key)
#   compose-project  the compose project name of the running stack
#   client-cn        a client whose CN names an active endpoint (default: alice)
# Variable: PROXY_PORT (default 8443). Needs curl, openssl and docker; no root, no ca.key.
# Exit status: 0 when every check passes, 1 when any fails, 2 on a usage or precondition error.
set -euo pipefail

CERTS=${1:-}
PROJECT=${2:-}
CLIENT=${3:-alice}
PORT=${PROXY_PORT:-8443}
URL="https://localhost:$PORT"
# What a client sees when the proxy refuses it during the handshake. A connection that is
# refused or times out matches none of these, so a stack that is down never reads as a refusal.
TLS_REFUSAL='(certificate required|handshake failure|unknown ca|bad certificate|unrecognized name|protocol version)'
FAILED=0
TMP=""

die() { echo "error: $*" >&2; exit 2; }
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; FAILED=1; }

cleanup() { [ -z "$TMP" ] || rm -rf -- "$TMP"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

preflight() {
  [ -n "$CERTS" ] && [ -n "$PROJECT" ] || die "usage: check-proxy.sh <certs-dir> <compose-project> [client-cn]"
  local c
  for c in curl openssl docker; do
    command -v "$c" >/dev/null 2>&1 || die "$c is required and not on PATH"
  done
  for c in ca.crt localhost.crt localhost.key "$CLIENT.crt" "$CLIENT.key"; do
    [ -r "$CERTS/$c" ] || die "cannot read $CERTS/$c"
  done
  PROXY=$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=proxy")
  [ -n "$PROXY" ] && [ "$(printf '%s\n' "$PROXY" | wc -l)" -eq 1 ] \
    || fail "proxy container for project $PROJECT found exactly once"
  TMP=$(umask 077 && mktemp -d)
}

# A second CA with a client certificate the real CA never signed.
make_rogue() {
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=RogueCA" \
    -keyout "$TMP/rogue-ca.key" -out "$TMP/rogue-ca.crt" 2>/dev/null
  openssl req -newkey rsa:2048 -nodes -subj "/CN=bob" -keyout "$TMP/bob.key" \
    -out "$TMP/bob.csr" 2>/dev/null
  printf 'extendedKeyUsage=clientAuth\n' >"$TMP/ext.cnf"
  openssl x509 -req -in "$TMP/bob.csr" -CA "$TMP/rogue-ca.crt" -CAkey "$TMP/rogue-ca.key" \
    -CAcreateserial -days 1 -extfile "$TMP/ext.cnf" -out "$TMP/bob.crt" 2>/dev/null
}

# base64 of the DER certificate, the form the proxy puts in X-Forwarded-Tls-Client-Cert.
der_b64() { openssl x509 -in "$1" -outform DER | openssl base64 -A; }

# Valid client over a route: prints the status code on line 1 and the body after it.
valid_get() {
  curl --silent --show-error --max-time 10 --cacert "$CERTS/ca.crt" \
    --cert "$CERTS/$CLIENT.crt" --key "$CERTS/$CLIENT.key" \
    --write-out '\n%{http_code}\n' "$@" 2>&1 || true
}

# True when the valid client reaches its own endpoint; the control for every refusal.
control_ok() {
  local out
  out=$(valid_get "$URL/endpoint/me")
  [ "$(printf '%s\n' "$out" | tail -n 1)" = 200 ] && printf '%s' "$out" | /usr/bin/grep -qF "\"certificate_dn\":\"$CLIENT\""
}

# refuse_tls <name> <curl args...>: the control passes, then the handshake is refused.
refuse_tls() {
  local name=$1 err rc=0
  shift
  control_ok || { fail "$name (control: valid client did not get 200, stack is down or misconfigured)"; return; }
  err=$(curl --silent --show-error --max-time 10 --output /dev/null "$@" 2>&1) || rc=$?
  if [ "$rc" -eq 0 ]; then
    fail "$name (handshake accepted)"
  elif printf '%s' "$err" | /usr/bin/grep -qE "$TLS_REFUSAL"; then
    pass "$name"
  else
    fail "$name (not a TLS refusal, curl exit $rc)"
  fi
}

check_refusals() {
  refuse_tls "no client certificate is refused" --cacert "$CERTS/ca.crt" "$URL/"
  refuse_tls "certificate from a second CA is refused" --cacert "$CERTS/ca.crt" \
    --cert "$TMP/bob.crt" --key "$TMP/bob.key" "$URL/"
  refuse_tls "server certificate used as a client is refused" --cacert "$CERTS/ca.crt" \
    --cert "$CERTS/localhost.crt" --key "$CERTS/localhost.key" "$URL/"
  refuse_tls "wrong server name is refused" --cacert "$CERTS/ca.crt" \
    --cert "$CERTS/$CLIENT.crt" --key "$CERTS/$CLIENT.key" \
    --resolve "other.invalid:$PORT:127.0.0.1" "https://other.invalid:$PORT/"
  refuse_tls "missing server name (IP address) is refused" --cacert "$CERTS/ca.crt" \
    --cert "$CERTS/$CLIENT.crt" --key "$CERTS/$CLIENT.key" "https://127.0.0.1:$PORT/"
}

# TLS 1.1 goes through openssl: curl's own build may refuse to offer it, which would be
# the client failing and not the proxy refusing.
check_tls11() {
  local name="TLS 1.1 is refused" err
  local -a base=(s_client -connect "localhost:$PORT" -servername localhost -CAfile "$CERTS/ca.crt"
    -cert "$CERTS/$CLIENT.crt" -key "$CERTS/$CLIENT.key" -cipher 'ALL:@SECLEVEL=0')
  err=$(openssl "${base[@]}" -tls1_2 </dev/null 2>&1) || true
  printf '%s' "$err" | /usr/bin/grep -qE 'Cipher is [A-Z0-9]' \
    || { fail "$name (control: TLS 1.2 handshake failed)"; return; }
  err=$(openssl "${base[@]}" -tls1_1 </dev/null 2>&1) || true
  if printf '%s' "$err" | /usr/bin/grep -q 'alert protocol version'; then
    pass "$name"
  else
    fail "$name (no protocol version alert)"
  fi
}

check_valid_client() {
  local out forged
  out=$(valid_get "$URL/endpoint/me")
  if [ "$(printf '%s\n' "$out" | tail -n 1)" = 200 ] && printf '%s' "$out" | /usr/bin/grep -qF "\"certificate_dn\":\"$CLIENT\""; then
    pass "valid client gets 200 with its endpoint on /endpoint/me"
  else
    fail "valid client gets 200 with its endpoint on /endpoint/me"
  fi
  forged=$(der_b64 "$TMP/bob.crt")
  out=$(valid_get --header "X-Forwarded-Tls-Client-Cert: $forged" \
    --header "X-Forwarded-Tls-Client-Cert: $forged" \
    --header "X-Client-Cert-Subject: CN=bob" "$URL/endpoint/me")
  if [ "$(printf '%s\n' "$out" | tail -n 1)" = 200 ] && printf '%s' "$out" | /usr/bin/grep -qF "\"certificate_dn\":\"$CLIENT\""; then
    pass "forged forwarded certificate and subject header still give the valid client"
  else
    fail "forged forwarded certificate and subject header still give the valid client"
  fi
}

# The server must answer 401 to a forged header from anywhere but the proxy's address.
check_server_direct() {
  local server_ip forged code image net name out
  control_ok || { fail "direct server access gives 401 (control: valid client did not get 200)"; return; }
  net="${PROJECT}_app"
  server_ip=$(docker inspect --format "{{(index .NetworkSettings.Networks \"$net\").IPAddress}}" \
    "$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" \
      --filter "label=com.docker.compose.service=server")") || server_ip=""
  [ -n "$server_ip" ] || { fail "direct server access gives 401 (server address on $net not found)"; return; }
  forged=$(der_b64 "$CERTS/$CLIENT.crt")

  code=$(curl --silent --output /dev/null --max-time 10 --write-out '%{http_code}' \
    --header "X-Forwarded-Tls-Client-Cert: $forged" "http://$server_ip:8000/endpoint/me") || code=000
  if [ "$code" = 401 ]; then
    pass "host to the server address with a forged header gives 401"
  else
    fail "host to the server address with a forged header gives $code, expected 401"
  fi

  # A throwaway container on the app network, from an image the stack already pins by digest.
  image=$(docker inspect --format '{{.Config.Image}}' \
    "$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" \
      --filter "label=com.docker.compose.service=db")") || image=""
  case "$image" in *@sha256:*) ;; *) fail "app-network container gives 401 (db image is not pinned by digest)"; return ;; esac
  name="${PROJECT}-check-$$"
  # wget exits non-zero on the 401 itself, so its exit status says nothing; read the status line.
  out=$(docker run --rm --name "$name" --memory 64m --network "$net" "$image" \
    wget -q -S -O /dev/null --header "X-Forwarded-Tls-Client-Cert: $forged" \
    "http://$server_ip:8000/endpoint/me" 2>&1 || true)
  code=$(printf '%s\n' "$out" | sed -n 's/^ *HTTP\/[0-9.]* \([0-9]*\).*/\1/p' | head -n 1)
  if [ "$code" = 401 ]; then
    pass "container on the app network with a forged header gets 401"
  else
    fail "container on the app network with a forged header gets '${code:-no answer}', expected 401"
  fi
}

check_closed_ports() {
  local p rc
  for p in 8080 8082; do
    control_ok || { fail "host port $p is refused (control: valid client did not get 200)"; continue; }
    rc=0
    curl --silent --output /dev/null --max-time 5 "http://127.0.0.1:$p/" || rc=$?
    if [ "$rc" -eq 7 ]; then
      pass "host port $p is refused"
    else
      fail "host port $p is refused (curl exit $rc, expected 7)"
    fi
  done
}

check_mounts() {
  local mounts n bad
  [ -n "$PROXY" ] || { fail "proxy mounts could not be read (no proxy container)"; return; }
  mounts=$(docker inspect --format '{{range .Mounts}}{{.Source}}|{{.Destination}}|{{.RW}}{{"\n"}}{{end}}' "$PROXY") \
    || { fail "proxy mounts could not be read"; return; }
  n=$(printf '%s\n' "$mounts" | /usr/bin/grep -c '|/certs/' || true)
  bad=$(printf '%s\n' "$mounts" | /usr/bin/grep -E 'ca\.key|docker\.sock|\|true$' || true)
  if [ "$n" -eq 3 ] && [ -z "$bad" ]; then
    pass "proxy has exactly three certificate mounts, all read-only, no ca.key or docker.sock"
  else
    fail "proxy mounts: $n under /certs, offending entries: ${bad:-none}"
  fi
}

main() {
  preflight
  make_rogue
  check_valid_client
  check_refusals
  check_tls11
  check_server_direct
  check_closed_ports
  check_mounts
  [ "$FAILED" -eq 0 ] || { echo "one or more checks failed" >&2; exit 1; }
  echo "all checks passed"
}

main
