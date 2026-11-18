#!/usr/bin/env bash
# Checks that the compose stack's proxy is the committed one and the only way in, and that it
# verifies client certificates. It compares the RUNNING proxy with HEAD (image, entrypoint,
# command, environment, mounts, and the bytes of both Traefik files) and then tests behavior;
# it does not parse any proxy config. The two Traefik files must be committed and clean.
# Run it against a stack already started and seeded as described in README, "Compose".
# It does not start, stop or seed anything and never writes to the database.
#
# Out of scope: someone with Docker access acting on purpose (they can start a container at
# the proxy's address). This finds drift and mistakes, not an attacker with Docker.
#
# Usage: check-proxy.sh <certs-dir> <compose-project> [client-cn]
#   certs-dir        folder from generate-certs.sh (ca.crt, <client>.crt, <client>.key, localhost.crt/.key)
#   compose-project  the compose project name of the running stack
#   client-cn        a client whose CN names an active endpoint (default: alice)
# Run it on the Docker host, from a checkout: the mount sources must be readable here.
# Needs curl, openssl, docker and git, plus GNU coreutils (timeout, cmp, realpath, mktemp,
# date, sort, comm, head, tail, tr, wc, dirname, rm) and sed and /usr/bin/grep; no root, no ca.key.
# Exit status: 0 when every check passes, 1 when any fails, 2 on a usage or precondition error.
set -euo pipefail

CERTS=${1:-}
PROJECT=${2:-}
CLIENT=${3:-alice}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# The folder holding compose.yaml and traefik/, two levels above this script.
APP_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
# Ports as the stack defines them: the proxy's own listener, the server, the Traefik API and
# the proxy's ping listener inside the container.
PROXY_CONTAINER_PORT=8443
SERVER_PORT=8000
TRAEFIK_API_PORT=8080
PING_PORT=8082
# Upper bound in seconds for every call that waits on the network, and for every docker call.
NET_TIMEOUT=10
DOCKER_TIMEOUT=30
PORT=""
URL=""
# What a client sees when the proxy refuses it during the handshake. A connection that is
# refused or times out matches none of these, so a stack that is down never reads as a refusal.
TLS_REFUSAL='(certificate required|handshake failure|unknown ca|bad certificate|unrecognized name|protocol version)'
FAILED=0
TMP=""
CONTAINER=""
PROXY=""
APP_NET=""
PROXY_IP=""
PORTS=""
STATIC_SRC=""
SERVER_IP=""
PINNED=""
CA_REAL=""
CRT_REAL=""
KEY_REAL=""
DYNAMIC_SRC=""
GIT_PREFIX=""
THROWAWAY_IMAGE=""

die() { echo "error: $*" >&2; exit 2; }
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; FAILED=1; }

# Every external call below goes through one of these, so a hung daemon, server or listener
# ends as a failure after a bound and never as a hang. -k 5 follows up with KILL. --foreground
# keeps the command in the script's process group, so guarded_main can stop it with a signal.
dk() { timeout --foreground -k 5 "$DOCKER_TIMEOUT" docker "$@"; }
curl_t() { timeout --foreground -k 5 $((NET_TIMEOUT + 5)) curl "$@"; }
ossl() { timeout --foreground -k 5 30 openssl "$@"; }

cleanup() {
  [ -z "$TMP" ] || rm -rf -- "$TMP"
  # The throwaway container normally removes itself (--rm), so "no such container" is the
  # expected failure here; a container left by an interrupted or timed-out run is removed.
  # Its name is fixed in guarded_main because a $(...) call cannot hand a name back.
  # This is a cleanup, not a read of state a check depends on.
  [ -z "$CONTAINER" ] || dk rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# The only running container of a compose service, or an error: a second one would make
# every later check read the wrong container.
service_container() {
  local id
  id=$(dk ps -q --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=$1") || die "cannot list the containers of project $PROJECT"
  [ -n "$id" ] || die "no running $1 container for project $PROJECT"
  [ "$(printf '%s\n' "$id" | wc -l)" -eq 1 ] || die "more than one $1 container for project $PROJECT"
  printf '%s\n' "$id"
}

preflight() {
  [ -n "$CERTS" ] && [ -n "$PROJECT" ] || die "usage: check-proxy.sh <certs-dir> <compose-project> [client-cn]"
  local c line endpoint
  for c in curl openssl docker git timeout cmp realpath mktemp date sed sort comm head tail tr wc dirname rm; do
    command -v "$c" >/dev/null 2>&1 || die "$c is required and not on PATH"
  done
  [ -x /usr/bin/grep ] || die "/usr/bin/grep is required"
  # Mount sources are host paths; a remote daemon would show paths this host cannot read.
  case "${DOCKER_HOST:-unix://}" in unix://*) ;; *) die "DOCKER_HOST is remote; run this on the Docker host" ;; esac
  # The same holds for the active context, which DOCKER_CONTEXT or the CLI config can point
  # at a remote daemon without touching DOCKER_HOST.
  endpoint=$(dk context inspect --format '{{.Endpoints.docker.Host}}') \
    || die "cannot read the active docker context"
  case "$endpoint" in unix://*) ;; *) die "the active docker context points at ${endpoint:-nothing}; run this on the Docker host" ;; esac
  for c in ca.crt localhost.crt localhost.key "$CLIENT.crt" "$CLIENT.key"; do
    [ -r "$CERTS/$c" ] || die "cannot read $CERTS/$c"
  done
  for c in ca.crt localhost.crt "$CLIENT.crt"; do
    ossl x509 -in "$CERTS/$c" -noout >/dev/null 2>&1 || die "$CERTS/$c is not a readable certificate"
  done
  GIT_PREFIX=$(git -C "$APP_DIR" rev-parse --show-prefix) || die "$APP_DIR is not inside a git checkout"
  git -C "$APP_DIR" rev-parse --verify --quiet HEAD >/dev/null || die "the checkout has no HEAD commit"
  [ -n "$TMP" ] || die "internal error: no temporary folder"
  dk info >/dev/null 2>&1 || die "the docker daemon does not answer"
  PROXY=$(service_container proxy)
  # All published ports, for example "8443/tcp -> 127.0.0.1:8443".
  PORTS=$(dk port "$PROXY") || die "cannot list the published ports of the proxy"
  line=$(dk port "$PROXY" "$PROXY_CONTAINER_PORT/tcp") \
    || die "the proxy publishes no host port for $PROXY_CONTAINER_PORT/tcp"
  line=${line%%$'\n'*}
  PORT=${line##*:}
  case "$PORT" in '' | *[!0-9]*) die "cannot read a port from 'docker port': $line" ;; esac
  URL="https://localhost:$PORT"
  APP_NET="${PROJECT}_app"
  PROXY_IP=$(dk inspect --format "{{(index .NetworkSettings.Networks \"$APP_NET\").IPAddress}}" "$PROXY") \
    || die "cannot read the proxy address on $APP_NET"
  [ -n "$PROXY_IP" ] || die "the proxy has no address on $APP_NET"
  # The throwaway containers use an image the stack already pins by digest and has locally.
  THROWAWAY_IMAGE=$(dk inspect --format '{{.Config.Image}}' "$(service_container db)") \
    || die "cannot read the db image"
  case "$THROWAWAY_IMAGE" in *@sha256:*) ;; *) die "the db image is not pinned by digest" ;; esac
  # Everything a check needs from outside the running stack is read here, so that once the
  # checks start a problem is a failed check and never an early exit that skips the rest.
  SERVER_IP=$(dk inspect --format "{{(index .NetworkSettings.Networks \"$APP_NET\").IPAddress}}" \
    "$(service_container server)") || die "cannot read the server address on $APP_NET"
  [ -n "$SERVER_IP" ] || die "the server has no address on $APP_NET"
  for c in traefik.yml dynamic.yml; do
    git -C "$APP_DIR" show "HEAD:${GIT_PREFIX}traefik/$c" >"$TMP/head-$c" \
      || die "traefik/$c is not committed at HEAD"
  done
  PINNED=$(git -C "$APP_DIR" show "HEAD:${GIT_PREFIX}compose.yaml" \
    | /usr/bin/grep -oE 'traefik:[^ ]+@sha256:[0-9a-f]{64}' | sort -u) || die "no pinned traefik image in compose.yaml at HEAD"
  [ -n "$PINNED" ] && [ "$(printf '%s\n' "$PINNED" | wc -l)" -eq 1 ] \
    || die "compose.yaml at HEAD must pin exactly one traefik image"
  CA_REAL=$(realpath -e -- "$CERTS/ca.crt") || die "cannot resolve $CERTS/ca.crt"
  CRT_REAL=$(realpath -e -- "$CERTS/localhost.crt") || die "cannot resolve $CERTS/localhost.crt"
  KEY_REAL=$(realpath -e -- "$CERTS/localhost.key") || die "cannot resolve $CERTS/localhost.key"
}

# A second CA with a client certificate the real CA never signed.
make_rogue() {
  ossl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=RogueCA" \
    -keyout "$TMP/rogue-ca.key" -out "$TMP/rogue-ca.crt" 2>/dev/null || return 1
  ossl req -newkey rsa:2048 -nodes -subj "/CN=bob" -keyout "$TMP/bob.key" \
    -out "$TMP/bob.csr" 2>/dev/null || return 1
  printf 'extendedKeyUsage=clientAuth\n' >"$TMP/ext.cnf" || return 1
  ossl x509 -req -in "$TMP/bob.csr" -CA "$TMP/rogue-ca.crt" -CAkey "$TMP/rogue-ca.key" \
    -CAcreateserial -days 1 -extfile "$TMP/ext.cnf" -out "$TMP/bob.crt" 2>/dev/null || return 1
  ossl x509 -in "$TMP/bob.crt" -noout >/dev/null 2>&1 || return 1
}

# base64 of the DER certificate, the form the proxy puts in X-Forwarded-Tls-Client-Cert.
der_b64() { ossl x509 -in "$1" -outform DER | ossl base64 -A; }

# Valid client over a route: prints the status code on line 1 and the body after it.
valid_get() {
  # curl exits non-zero on a refusal or a timeout. Its message and the 000 status that
  # --write-out prints end up in the output, which the caller reads as "not 200".
  curl_t --silent --show-error --max-time "$NET_TIMEOUT" --cacert "$CERTS/ca.crt" \
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
  err=$(curl_t --silent --show-error --max-time "$NET_TIMEOUT" --output /dev/null "$@" 2>&1) || rc=$?
  if [ "$rc" -eq 0 ]; then
    fail "$name (handshake accepted)"
  elif printf '%s' "$err" | /usr/bin/grep -qE "$TLS_REFUSAL"; then
    pass "$name"
  else
    fail "$name (not a TLS refusal, curl exit $rc)"
  fi
}

# Certificates in a PEM file: prints the count, or fails when the file cannot be read
# (grep exits 1 for a count of 0, and 2 for an error).
cert_count() {
  local n rc=0
  n=$(/usr/bin/grep -c '^-----BEGIN [A-Z0-9 ]*CERTIFICATE-----' "$1") || rc=$?
  [ "$rc" -le 1 ] || return 1
  printf '%s\n' "$n"
}

# The proxy trusts every certificate in ca.crt, and the server does not check the issuer, so a
# second CA in the file lets its clients in under any name. Both copies are counted: the one
# the proxy holds catches a proxy started on two CAs and left alone, and the host one catches
# a source repointed after start, which the next start would load.
check_ca_bundle() {
  local msg="ca.crt holds exactly one certificate, on the host and inside the proxy" host run bad=""
  host=$(cert_count "$CA_REAL") || host=unreadable
  if dk exec "$PROXY" cat /certs/ca.crt >"$TMP/run-ca.crt"; then
    run=$(cert_count "$TMP/run-ca.crt") || run=unreadable
  else
    run=unreadable
  fi
  [ "$host" = 1 ] || bad+="host copy $CA_REAL has $host; "
  [ "$run" = 1 ] || bad+="the proxy's copy has $run; "
  if [ -z "$bad" ]; then
    pass "$msg"
  else
    fail "$msg (${bad%; })"
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
s_client() { timeout --foreground -k 5 "$NET_TIMEOUT" openssl s_client "$@" </dev/null 2>&1; }

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

# The proxy should replace whatever a client sends in the certificate header at the
# entrypoint, so this cannot fail on its own today. It stays as defense in depth: it is the
# check that notices if a later change lets a client-supplied header through.
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

# Runs a command in a throwaway container on the app network and prints its output. The
# exit status is the command's, or 124 and 137 when the outer limit ended it.
run_throwaway() {
  timeout --foreground -k 5 60 docker run --rm --init --name "$CONTAINER" --memory 64m --memory-swap 64m \
    --cap-drop ALL --security-opt no-new-privileges --pids-limit 64 --user 65534:65534 \
    --read-only --pull never --network "$APP_NET" "$THROWAWAY_IMAGE" "$@" 2>&1
}

# The server must answer 401 to a forged header from anywhere but the proxy's address.
check_server_direct() {
  local server_ip=$SERVER_IP forged code out rc=0
  control_ok || { fail "direct server access gives 401 (control: valid client did not get 200)"; return; }
  forged=$(der_b64 "$CERTS/$CLIENT.crt")

  code=$(curl_t --silent --output /dev/null --max-time "$NET_TIMEOUT" --write-out '%{http_code}' \
    --header "X-Forwarded-Tls-Client-Cert: $forged" "http://$server_ip:$SERVER_PORT/endpoint/me") || code=000
  if [ "$code" = 401 ]; then
    pass "host to the server address with a forged header gives 401"
  else
    fail "host to the server address with a forged header gives $code, expected 401"
  fi

  # wget exits non-zero on the 401 itself, and docker exits non-zero when the outer time
  # limit kills it; in both cases the answer is read from the status line, or its absence.
  out=$(run_throwaway wget -q -T "$NET_TIMEOUT" -S -O /dev/null \
    --header "X-Forwarded-Tls-Client-Cert: $forged" "http://$server_ip:$SERVER_PORT/endpoint/me") || rc=$?
  code=$(printf '%s\n' "$out" | sed -n 's/^ *HTTP\/[0-9.]* \([0-9]*\).*/\1/p' | head -n 1)
  if [ "$code" = 401 ]; then
    pass "container on the app network with a forged header gets 401"
  else
    fail "container on the app network with a forged header gets '${code:-no answer}' (exit $rc), expected 401"
  fi
}

# From inside the app network the proxy's own listener must answer and its API and ping
# ports must not. The :8443 answer is the control: without it a dead network would read
# as a refusal of the other two.
check_app_network_ports() {
  local out rc=0 p
  # Runs inside the container: <address> <port>... gives one "<port> open|closed" line each.
  # shellcheck disable=SC2016 # the container's shell expands these, not this one
  local probe='h=$1; shift; for p in "$@"; do
    if nc -z -w 3 "$h" "$p"; then echo "$p open"; else echo "$p closed"; fi; done'
  out=$(run_throwaway sh -c "$probe" sh "$PROXY_IP" "$PROXY_CONTAINER_PORT" "$TRAEFIK_API_PORT" "$PING_PORT") || rc=$?
  if ! printf '%s\n' "$out" | /usr/bin/grep -qx "$PROXY_CONTAINER_PORT open"; then
    fail "proxy API and ping ports are refused on the app network (control: :$PROXY_CONTAINER_PORT not reachable, exit $rc)"
    return
  fi
  for p in "$TRAEFIK_API_PORT" "$PING_PORT"; do
    if printf '%s\n' "$out" | /usr/bin/grep -qx "$p closed"; then
      pass "proxy port $p is refused from the app network"
    else
      fail "proxy port $p is refused from the app network (not refused)"
    fi
  done
}

# Only the proxy's own port may be published, so the API and ping listeners are never
# reachable from the host, whatever address they bind inside the container.
check_published_ports() {
  local msg="the proxy publishes only $PROXY_CONTAINER_PORT/tcp" total ok
  total=$(printf '%s\n' "$PORTS" | wc -l)
  # grep -c prints 0 and exits 1 when no line matches; that count is the answer.
  ok=$(printf '%s\n' "$PORTS" | /usr/bin/grep -c "^$PROXY_CONTAINER_PORT/tcp -> " || true)
  if [ "$ok" -ge 1 ] && [ "$ok" -eq "$total" ]; then
    pass "$msg"
  else
    fail "$msg (docker port lists: $(printf '%s' "$PORTS" | tr '\n' ' '))"
  fi
}

# Both Traefik files are byte-identical to the ones committed at HEAD, on the host and as the
# proxy itself reads them. A single-file bind mount pins the file the proxy started with, so a
# host file replaced afterwards is a new file the proxy never sees. The copy read inside the
# container is the one the proxy holds open; it is what the proxy loaded only together with
# check_unchanged_since_start. (docker cp reads the host path, so it is no substitute.) Needs
# check_mounts to have run first, since that sets the sources.
check_committed_config() {
  local name src msg host_diff run_diff
  for name in traefik.yml dynamic.yml; do
    if [ "$name" = traefik.yml ]; then src=$STATIC_SRC; else src=$DYNAMIC_SRC; fi
    msg="mounted $name is identical to the committed file"
    if [ -z "$src" ]; then
      fail "$msg (no mount found for it)"
    elif [ ! -r "$src" ]; then
      fail "$msg (host copy $src is not readable on this host)"
    elif ! dk exec "$PROXY" cat "/etc/traefik/$name" >"$TMP/run-$name"; then
      fail "$msg (cannot read the proxy's copy, /etc/traefik/$name)"
    else
      host_diff=0 run_diff=0
      cmp -s "$src" "$TMP/head-$name" || host_diff=1
      cmp -s "$TMP/run-$name" "$TMP/head-$name" || run_diff=1
      if [ "$host_diff" -eq 0 ] && [ "$run_diff" -eq 0 ]; then
        pass "$msg"
      elif [ "$host_diff" -ne 0 ] && [ "$run_diff" -ne 0 ]; then
        fail "mounted $name differs from the committed file on the host ($src) and in the proxy"
      elif [ "$host_diff" -ne 0 ]; then
        fail "mounted $name differs from the committed file on the host ($src); the proxy's copy matches"
      else
        fail "mounted $name differs from the committed file in the proxy; the host copy matches, so the proxy started on other bytes or the file was replaced after start; recreate the proxy"
      fi
    fi
  done
}

# The image the proxy runs is the one compose.yaml pins, and it starts with the image's own
# entrypoint, command and environment: nothing swaps the program or feeds it settings.
check_image_and_launch() {
  local msg="proxy runs the pinned image" have image_id want got field
  have=$(dk inspect --format '{{.Config.Image}}' "$PROXY") || have=""
  image_id=$(dk inspect --format '{{.Image}}' "$PROXY") || image_id=""
  want=$(dk image inspect --format '{{.Id}}' "$PINNED") || want=""
  if [ "$have" != "$PINNED" ]; then
    fail "$msg (running ${have:-unreadable}, committed $PINNED)"
  elif [ -n "$image_id" ] && [ "$image_id" = "$want" ]; then
    pass "$msg"
  else
    fail "$msg (image id ${image_id:-unreadable} differs from ${want:-unreadable})"
  fi
  for field in Entrypoint Env; do
    msg="proxy $field equals the image's own"
    got=$(dk inspect --format "{{json .Config.$field}}" "$PROXY") || got=""
    want=""
    [ -z "$image_id" ] || want=$(dk image inspect --format "{{json .Config.$field}}" "$image_id") || want=""
    case "$got" in
      '' | null | '[]') fail "$msg (the proxy $field is empty or unreadable; cannot compare it)"; continue ;;
    esac
    if [ "$got" = "$want" ]; then
      pass "$msg"
    else
      fail "$msg (running $got, image ${want:-unreadable})"
    fi
  done
  got=$(dk inspect --format '{{json .Config.Cmd}}' "$PROXY") || got=""
  if [ "$got" = '["traefik"]' ]; then
    pass "proxy command is [traefik]"
  else
    fail "proxy command is [traefik] (running ${got:-unreadable})"
  fi
  got=$(dk inspect --format '{{json .HostConfig.Tmpfs}}' "$PROXY") || got=""
  case "$got" in null | '{}') pass "proxy has no tmpfs" ;; *) fail "proxy has no tmpfs (found ${got:-unreadable})" ;; esac
}

# Nanoseconds since the epoch for a timestamp, or failure. GNU date reads both the daemon's
# StartedAt and stat's %z; the empty string is refused because date takes it as midnight.
to_ns() {
  local ns
  [ -n "$1" ] || return 1
  ns=$(date -d "$1" +%s%N 2>/dev/null) || return 1
  case "$ns" in '' | *[!0-9]*) return 1 ;; esac
  printf '%s\n' "$ns"
}

started_ns() {
  local started
  started=$(dk inspect --format '{{.State.StartedAt}}' "$PROXY") || return 1
  to_ns "$started"
}

# Traefik reads its static config and the CA file once, at start, so a file read now cannot
# show what it loaded. Nothing it mounted may have changed since it started: ctime, which user
# space cannot set (mtime can be set back), read inside the proxy where the held inode is, in
# nanoseconds because busybox's whole-second %Z would miss a change in the start's own second.
# StartedAt, never Created: docker restart moves StartedAt and reloads the files. A restore
# after start fails too; recreate the proxy.
check_unchanged_since_start() {
  local msg="proxy files unchanged since the proxy started" start out name ts ns dst
  local changed="" bad="" seen="|" missing=""
  local -a dsts=(/certs/ca.crt /certs/server.crt /certs/server.key /etc/traefik/traefik.yml /etc/traefik/dynamic.yml)
  start=$(started_ns) || { fail "$msg (cannot read when the proxy started)"; return; }
  out=$(dk exec "$PROXY" stat -c '%n|%z' "${dsts[@]}") \
    || { fail "$msg (cannot read the file times inside the proxy)"; return; }
  while IFS='|' read -r name ts; do
    [ -n "$name" ] || continue
    case " ${dsts[*]} " in
      *" $name "*) seen+="$name|" ;;
      *) bad+="$name (unexpected file) "; continue ;;
    esac
    if ns=$(to_ns "$ts"); then
      if [ "$ns" -gt "$start" ]; then changed+="$name "; fi
    else
      bad+="$name (time '$ts' not readable) "
    fi
  done <<<"$out"
  for dst in "${dsts[@]}"; do
    case "$seen" in *"|$dst|"*) ;; *) missing+="$dst " ;; esac
  done
  if [ -n "$changed" ] || [ -n "$bad" ] || [ -n "$missing" ]; then
    fail "$msg (changed after start: ${changed:-none}; unreadable: ${bad:-none}; missing: ${missing:-none}; recreate the proxy: up -d --force-recreate proxy)"
  else
    pass "$msg"
  fi
}

# The proxy's mounts must be exactly: three single certificate files and the two config
# files, all bind mounts and read-only. A folder, a volume, a tmpfs or a socket is a failure.
# The config sources are compared by content in check_committed_config; here they stand in
# as CONFIG so their path does not matter.
check_mounts() {
  local msg="proxy mounts are exactly the three certificate files and two config files, read-only"
  local mounts actual expected type src dst rw extra missing
  mounts=$(dk inspect --format '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{"\n"}}{{end}}' "$PROXY") \
    || { fail "$msg (cannot read the proxy mounts)"; return; }
  actual=""
  while IFS='|' read -r type src dst rw; do
    [ -n "$type" ] || continue
    case "$dst" in
      /etc/traefik/traefik.yml) STATIC_SRC=$src; src=CONFIG ;;
      /etc/traefik/dynamic.yml) DYNAMIC_SRC=$src; src=CONFIG ;;
      # Real paths, so a symlinked folder does not read as a different file; a source that
      # does not resolve stays empty and matches nothing.
      *) src=$(realpath -e -- "$src" 2>/dev/null) || src="" ;;
    esac
    actual+="$type|$src|$dst|$rw"$'\n'
  done <<<"$mounts"
  actual=$(printf '%s' "$actual" | LC_ALL=C sort)
  expected=$(printf '%s\n' \
    "bind|$CA_REAL|/certs/ca.crt|false" \
    "bind|$CRT_REAL|/certs/server.crt|false" \
    "bind|$KEY_REAL|/certs/server.key|false" \
    "bind|CONFIG|/etc/traefik/traefik.yml|false" \
    "bind|CONFIG|/etc/traefik/dynamic.yml|false" \
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
  check_ca_bundle
  check_refusals
  check_tls11
  check_server_direct
  check_app_network_ports
  check_published_ports
  check_mounts
  check_unchanged_since_start
  check_committed_config
  check_image_and_launch
  [ "$FAILED" -eq 0 ] || { echo "one or more checks failed" >&2; exit 1; }
  echo "all checks passed"
}

# Runs main as a job in its own process group and waits for it. A trap runs at once while the
# shell is in wait, but only after a foreground command or $(...) ends, so INT and TERM
# during a hung call would otherwise wait out its time bound. On a signal the whole group
# is stopped, and the EXIT trap then removes the temporary folder and the throwaway container.
guarded_main() {
  local pid rc=0
  TMP=$(umask 077 && mktemp -d) || die "cannot make a temporary folder"
  [ -z "$PROJECT" ] || CONTAINER="${PROJECT}-check-$$"
  set -m
  main &
  pid=$!
  trap 'kill -TERM -- "-$pid" 2>/dev/null || true; exit 130' INT
  trap 'kill -TERM -- "-$pid" 2>/dev/null || true; exit 143' TERM
  wait "$pid" || rc=$?
  exit "$rc"
}

# Sourcing the file loads the functions without running anything, so a test can call one.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then guarded_main; fi
