#!/usr/bin/env bash
# Checks that the compose stack's proxy is the only way in and verifies client certificates.
# Run it against a stack already started and seeded as described in README, "Compose".
# It does not start, stop or seed anything and never writes to the database.
#
# Usage: check-proxy.sh <certs-dir> <compose-project> [client-cn]
#   certs-dir        folder from generate-certs.sh (ca.crt, <client>.crt, <client>.key, localhost.crt/.key)
#   compose-project  the compose project name of the running stack
#   client-cn        a client whose CN names an active endpoint (default: alice)
# The port is read from the running proxy (docker port), not from a variable.
# Needs curl, openssl and docker, plus the base tools awk, sed, sort, comm, readlink and
# timeout; no root, no ca.key.
# Exit status: 0 when every check passes, 1 when any fails, 2 on a usage or precondition error.
set -euo pipefail

CERTS=${1:-}
PROJECT=${2:-}
CLIENT=${3:-alice}
# Ports as the stack defines them: the proxy's own listener, the server, the Traefik API and
# the proxy's ping listener inside the container.
PROXY_CONTAINER_PORT=8443
SERVER_PORT=8000
TRAEFIK_API_PORT=8080
PING_PORT=8082
# Upper bound in seconds for every call that waits on the network.
NET_TIMEOUT=10
PORT=""
URL=""
# What a client sees when the proxy refuses it during the handshake. A connection that is
# refused or times out matches none of these, so a stack that is down never reads as a refusal.
TLS_REFUSAL='(certificate required|handshake failure|unknown ca|bad certificate|unrecognized name|protocol version)'
FAILED=0
TMP=""
CONTAINER=""
PROXY=""
STATIC=""
DYNAMIC=""

die() { echo "error: $*" >&2; exit 2; }
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; FAILED=1; }

cleanup() {
  [ -z "$TMP" ] || rm -rf -- "$TMP"
  # The throwaway container normally removes itself (--rm), so "no such container" is the
  # expected failure here; a container left by an interrupted or timed-out run is removed.
  [ -z "$CONTAINER" ] || docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Comments out of a config file, so a word in a comment never counts as a setting.
strip_comments() { sed -e 's/^[[:space:]]*#.*$//' -e 's/[[:space:]]#.*$//'; }

preflight() {
  [ -n "$CERTS" ] && [ -n "$PROJECT" ] || die "usage: check-proxy.sh <certs-dir> <compose-project> [client-cn]"
  local c line
  for c in curl openssl docker timeout awk sed sort comm readlink; do
    command -v "$c" >/dev/null 2>&1 || die "$c is required and not on PATH"
  done
  for c in ca.crt localhost.crt localhost.key "$CLIENT.crt" "$CLIENT.key"; do
    [ -r "$CERTS/$c" ] || die "cannot read $CERTS/$c"
  done
  for c in ca.crt localhost.crt "$CLIENT.crt"; do
    openssl x509 -in "$CERTS/$c" -noout >/dev/null 2>&1 || die "$CERTS/$c is not a readable certificate"
  done
  timeout 20 docker info >/dev/null 2>&1 || die "the docker daemon does not answer"
  PROXY=$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=proxy") || die "cannot list the containers of project $PROJECT"
  [ -n "$PROXY" ] || die "no running proxy container for project $PROJECT"
  [ "$(printf '%s\n' "$PROXY" | wc -l)" -eq 1 ] || die "more than one proxy container for project $PROJECT"
  # The first published address of the proxy's own port, for example 127.0.0.1:8443.
  line=$(docker port "$PROXY" "$PROXY_CONTAINER_PORT/tcp") \
    || die "the proxy publishes no host port for $PROXY_CONTAINER_PORT/tcp"
  line=${line%%$'\n'*}
  PORT=${line##*:}
  case "$PORT" in '' | *[!0-9]*) die "cannot read a port from 'docker port': $line" ;; esac
  URL="https://localhost:$PORT"
  STATIC=$(docker exec "$PROXY" cat /etc/traefik/traefik.yml | strip_comments) \
    || die "cannot read /etc/traefik/traefik.yml in the proxy"
  DYNAMIC=$(docker exec "$PROXY" cat /etc/traefik/dynamic.yml | strip_comments) \
    || die "cannot read /etc/traefik/dynamic.yml in the proxy"
  [ -n "$STATIC" ] && [ -n "$DYNAMIC" ] || die "a proxy config file is empty"
  TMP=$(umask 077 && mktemp -d) || die "cannot make a temporary folder"
}

# A second CA with a client certificate the real CA never signed.
make_rogue() {
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=RogueCA" \
    -keyout "$TMP/rogue-ca.key" -out "$TMP/rogue-ca.crt" 2>/dev/null || return 1
  openssl req -newkey rsa:2048 -nodes -subj "/CN=bob" -keyout "$TMP/bob.key" \
    -out "$TMP/bob.csr" 2>/dev/null || return 1
  printf 'extendedKeyUsage=clientAuth\n' >"$TMP/ext.cnf" || return 1
  openssl x509 -req -in "$TMP/bob.csr" -CA "$TMP/rogue-ca.crt" -CAkey "$TMP/rogue-ca.key" \
    -CAcreateserial -days 1 -extfile "$TMP/ext.cnf" -out "$TMP/bob.crt" 2>/dev/null || return 1
  openssl x509 -in "$TMP/bob.crt" -noout >/dev/null 2>&1 || return 1
}

# base64 of the DER certificate, the form the proxy puts in X-Forwarded-Tls-Client-Cert.
der_b64() { openssl x509 -in "$1" -outform DER | openssl base64 -A; }

# Valid client over a route: prints the status code on line 1 and the body after it.
valid_get() {
  # curl exits non-zero on a refusal or a timeout. Its message and the 000 status that
  # --write-out prints end up in the output, which the caller reads as "not 200".
  curl --silent --show-error --max-time "$NET_TIMEOUT" --cacert "$CERTS/ca.crt" \
    --cert "$CERTS/$CLIENT.crt" --key "$CERTS/$CLIENT.key" \
    --write-out '\n%{http_code}\n' "$@" 2>&1 || true
}

# True when valid_get output <out> is a 200 whose body names this client's endpoint.
is_client_200() {
  [ "$(printf '%s\n' "$1" | tail -n 1)" = 200 ] \
    && printf '%s' "$1" | /usr/bin/grep -qF "\"certificate_dn\":\"$CLIENT\""
}

# True when the valid client reaches its own endpoint; the control for every refusal.
control_ok() { is_client_200 "$(valid_get "$URL/endpoint/me")"; }

# refuse_tls <name> <curl args...>: the control passes, then the handshake is refused.
refuse_tls() {
  local name=$1 err rc=0
  shift
  control_ok || { fail "$name (control: valid client did not get 200, stack is down or misconfigured)"; return; }
  err=$(curl --silent --show-error --max-time "$NET_TIMEOUT" --output /dev/null "$@" 2>&1) || rc=$?
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

# openssl s_client with a time limit; a listener that accepts and never answers ends as an
# empty result after NET_TIMEOUT, never as a hang.
s_client() { timeout "$NET_TIMEOUT" openssl s_client "$@" </dev/null 2>&1; }

# TLS 1.1 goes through openssl: curl's own build may refuse to offer it, which would be
# the client failing and not the proxy refusing.
check_tls11() {
  local name="TLS 1.1 is refused" err
  local -a base=(-connect "localhost:$PORT" -servername localhost -CAfile "$CERTS/ca.crt"
    -cert "$CERTS/$CLIENT.crt" -key "$CERTS/$CLIENT.key" -cipher 'ALL:@SECLEVEL=0')
  control_ok || { fail "$name (control: valid client did not get 200, stack is down or misconfigured)"; return; }
  # s_client exits non-zero when the handshake is refused or times out; both cases are
  # judged from its text below, so the status is not needed.
  err=$(s_client "${base[@]}" -tls1_2) || true
  printf '%s' "$err" | /usr/bin/grep -qE 'Cipher is [A-Z0-9]' \
    || { fail "$name (control: TLS 1.2 handshake failed)"; return; }
  err=$(s_client "${base[@]}" -tls1_1) || true
  if printf '%s' "$err" | /usr/bin/grep -q 'alert protocol version'; then
    pass "$name"
  else
    fail "$name (no protocol version alert)"
  fi
}

check_valid_client() {
  local out forged msg
  msg="valid client gets 200 with its endpoint on /endpoint/me"
  if is_client_200 "$(valid_get "$URL/endpoint/me")"; then pass "$msg"; else fail "$msg"; fi
  forged=$(der_b64 "$TMP/bob.crt")
  # The forged certificate is sent twice, so a proxy that replaced only one copy of the
  # header would leave a forged value for the server to read.
  out=$(valid_get --header "X-Forwarded-Tls-Client-Cert: $forged" \
    --header "X-Forwarded-Tls-Client-Cert: $forged" \
    --header "X-Client-Cert-Subject: CN=bob" "$URL/endpoint/me")
  msg="forged forwarded certificate and subject header still give the valid client"
  if is_client_200 "$out"; then pass "$msg"; else fail "$msg"; fi
}

# The server must answer 401 to a forged header from anywhere but the proxy's address.
check_server_direct() {
  local server_ip forged code image net out
  control_ok || { fail "direct server access gives 401 (control: valid client did not get 200)"; return; }
  net="${PROJECT}_app"
  server_ip=$(docker inspect --format "{{(index .NetworkSettings.Networks \"$net\").IPAddress}}" \
    "$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" \
      --filter "label=com.docker.compose.service=server")") || server_ip=""
  [ -n "$server_ip" ] || { fail "direct server access gives 401 (server address on $net not found)"; return; }
  forged=$(der_b64 "$CERTS/$CLIENT.crt")

  code=$(curl --silent --output /dev/null --max-time "$NET_TIMEOUT" --write-out '%{http_code}' \
    --header "X-Forwarded-Tls-Client-Cert: $forged" "http://$server_ip:$SERVER_PORT/endpoint/me") || code=000
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
  CONTAINER="${PROJECT}-check-$$"
  # wget exits non-zero on the 401 itself, and docker exits non-zero when the outer time
  # limit kills it; in both cases the answer is read from the status line, or its absence.
  out=$(timeout 60 docker run --rm --name "$CONTAINER" --memory 64m --memory-swap 64m \
    --cap-drop ALL --read-only --pull never --network "$net" "$image" \
    wget -q -T "$NET_TIMEOUT" -S -O /dev/null --header "X-Forwarded-Tls-Client-Cert: $forged" \
    "http://$server_ip:$SERVER_PORT/endpoint/me" 2>&1) || true
  code=$(printf '%s\n' "$out" | sed -n 's/^ *HTTP\/[0-9.]* \([0-9]*\).*/\1/p' | head -n 1)
  if [ "$code" = 401 ]; then
    pass "container on the app network with a forged header gets 401"
  else
    fail "container on the app network with a forged header gets '${code:-no answer}', expected 401"
  fi
}

check_closed_ports() {
  local p rc
  for p in "$TRAEFIK_API_PORT" "$PING_PORT"; do
    control_ok || { fail "host port $p is refused (control: valid client did not get 200)"; continue; }
    rc=0
    curl --silent --output /dev/null --max-time "$NET_TIMEOUT" "http://127.0.0.1:$p/" || rc=$?
    if [ "$rc" -eq 7 ]; then
      pass "host port $p is refused"
    else
      fail "host port $p is refused (curl exit $rc, expected 7)"
    fi
  done
}

# Prints "router <name> ok|missing|unreadable" per HTTP router in the dynamic config on
# stdin, "other <line>" for a tcp or udp section, and "routers <N>". A router is "ok" when
# its middlewares list names client-cert. Any shape this does not read is reported as a
# problem, never as ok. awk is used because the host needs no YAML parser for this one file.
router_report() {
  awk '
    function has_cc(s,   n, t, i) {
      n = split(s, t, /[][,"\047 ]+/)
      for (i = 1; i <= n; i++) if (t[i] == "client-cert" || t[i] == "client-cert@file") return 1
      return 0
    }
    function close_router() {
      if (name != "") { print "router " name " " (ok ? "ok" : "missing"); n++ }
      name = ""
    }
    NF == 0 { next }
    {
      match($0, /^ */); i = RLENGTH; line = substr($0, i + 1); sub(/[[:space:]]+$/, "", line)
      if (i == 0) {
        close_router(); in_http = (line ~ /^http:$/); in_routers = 0
        if (line ~ /^(tcp|udp):/) print "other " line
        next
      }
      if (!in_http) next
      if (in_routers && i <= rind) { close_router(); in_routers = 0 }
      if (!in_routers) {
        if (line ~ /^routers:$/) { in_routers = 1; rind = i; cind = -1 }
        next
      }
      if (cind < 0) cind = i
      if (i == cind) {
        close_router()
        name = line; sub(/:.*$/, "", name); ok = 0; in_mw = 0; pind = -1
        if (line !~ /:$/) { print "router " name " unreadable"; n++; name = "" }
        next
      }
      if (name == "") next
      if (pind < 0) pind = i
      if (i == pind && line ~ /^middlewares:/) {
        in_mw = 1; rest = line; sub(/^middlewares:/, "", rest); if (has_cc(rest)) ok = 1
        next
      }
      if (in_mw && line ~ /^- /) { if (has_cc(line)) ok = 1; next }
      if (i == pind) in_mw = 0
    }
    END { close_router(); print "routers " n + 0 }
  '
}

# The config the running proxy loaded, read from its own container. The server believes
# the forwarded certificate, so every route must pass through client-cert, and nothing may
# widen who is trusted to supply that header or expose the management API.
check_loaded_config() {
  local report bad cmd tenv
  report=$(printf '%s\n' "$DYNAMIC" | router_report)
  bad=$(printf '%s\n' "$report" | /usr/bin/grep -E '^(router .* (missing|unreadable)|other )' || true)
  if [ -n "$bad" ] || [ "$(printf '%s\n' "$report" | sed -n 's/^routers //p')" -lt 1 ]; then
    fail "every router carries the client-cert middleware, no tcp or udp routers (problems: ${bad:-no HTTP router found})"
  else
    pass "every router carries the client-cert middleware, no tcp or udp routers"
  fi
  if printf '%s\n%s\n' "$STATIC" "$DYNAMIC" | /usr/bin/grep -qi 'forwardedHeaders'; then
    fail "no forwardedHeaders setting anywhere in the proxy config"
  else
    pass "no forwardedHeaders setting anywhere in the proxy config"
  fi
  if printf '%s\n' "$STATIC" | /usr/bin/grep -qE "^[\"']?api[\"']?[[:space:]]*:"; then
    fail "no api key in the static config (dashboard and management API off)"
  else
    pass "no api key in the static config (dashboard and management API off)"
  fi
  # The two files read above are only the whole config if nothing else feeds the proxy.
  cmd=$(docker inspect --format '{{json .Config.Cmd}}' "$PROXY") || cmd=""
  # grep -c prints 0 and exits 1 when no variable starts with TRAEFIK_; that is the expected answer.
  tenv=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$PROXY" \
    | /usr/bin/grep -c '^TRAEFIK_' || true)
  if [ "$cmd" = '["traefik"]' ] && [ "$tenv" -eq 0 ] \
    && printf '%s\n' "$STATIC" | /usr/bin/grep -qE '^[[:space:]]+filename:[[:space:]]*/etc/traefik/dynamic\.yml$'; then
    pass "proxy settings come only from the two config files"
  else
    fail "proxy settings come only from the two config files (command ${cmd:-unknown}, $tenv TRAEFIK_ variables, or dynamic file not named in the static config)"
  fi
}

# The proxy's mounts must be exactly: three single certificate files and two config files,
# all bind mounts and read-only. Anything else, a folder or a socket included, is a failure.
check_mounts() {
  local msg="proxy mounts are exactly the three certificate files and two config files, read-only"
  local workdir actual expected type src dst rw extra missing
  workdir=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$PROXY") \
    || workdir=""
  [ -n "$workdir" ] || { fail "$msg (compose working directory label not found)"; return; }
  actual=$(docker inspect --format '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{"\n"}}{{end}}' "$PROXY") \
    || { fail "$msg (mounts could not be read)"; return; }
  # Sources compared as real paths, so a symlinked folder does not read as a different file.
  actual=$(printf '%s\n' "$actual" | while IFS='|' read -r type src dst rw; do
    [ -n "$type" ] || continue
    printf '%s|%s|%s|%s\n' "$type" "$(readlink -f "$src")" "$dst" "$rw"
  done | LC_ALL=C sort)
  expected=$(printf '%s\n' \
    "bind|$(readlink -f "$CERTS/ca.crt")|/certs/ca.crt|false" \
    "bind|$(readlink -f "$CERTS/localhost.crt")|/certs/server.crt|false" \
    "bind|$(readlink -f "$CERTS/localhost.key")|/certs/server.key|false" \
    "bind|$(readlink -f "$workdir/traefik/traefik.yml")|/etc/traefik/traefik.yml|false" \
    "bind|$(readlink -f "$workdir/traefik/dynamic.yml")|/etc/traefik/dynamic.yml|false" \
    | LC_ALL=C sort)
  if [ "$actual" = "$expected" ]; then
    pass "$msg"
  else
    extra=$(LC_ALL=C comm -13 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | tr '\n' ' ')
    missing=$(LC_ALL=C comm -23 <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") | tr '\n' ' ')
    fail "$msg (unexpected: ${extra:-none}; missing: ${missing:-none})"
  fi
}

main() {
  preflight
  make_rogue || die "cannot make the second CA and its client certificate with openssl"
  check_valid_client
  check_refusals
  check_tls11
  check_server_direct
  check_closed_ports
  check_loaded_config
  check_mounts
  [ "$FAILED" -eq 0 ] || { echo "one or more checks failed" >&2; exit 1; }
  echo "all checks passed"
}

# Sourcing the file loads the functions without running anything, so a test can call one.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then main; fi
