#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

SCRIPTS="$BATS_TEST_DIRNAME/.."
REPO_GITIGNORE="$BATS_TEST_DIRNAME/../../../.gitignore"
PG_SCRIPT="$SCRIPTS/generate-certs-from-existing-postgres.sh"
GEN_SCRIPT="$SCRIPTS/generate-certs.sh"
ALL_FILES="alice.crt alice.key alice.p12 ca.crt ca.key ca-trusted.crt"
REAL_HOME="${HOME:-}"

# The script refuses an output folder under a parent that others can write, so
# the tests cannot live under /tmp: each test gets a folder under the real home.
setup() {
    [ -n "$REAL_HOME" ] || skip "HOME is not set"
    TT=$(mktemp -d "$REAL_HOME/.uudex-certs-bats.XXXXXX")
    FAKE_HOME="$TT/home"
    WORKDIR="$TT/work"
    mkdir -p "$FAKE_HOME" "$WORKDIR"
    export HOME="$FAKE_HOME"
    unset UUDEX_CERTS UUDEX_CERTS_CONF DB_PASSWORD

    # psql stub: records each call and answers the three queries the script makes.
    STUB="$TT/stub"
    PSQL_LOG="$TT/psql.log"
    mkdir -p "$STUB"
    cat > "$STUB/psql" <<STUBEOF
#!/bin/sh
echo "called PGPASSWORD=\${PGPASSWORD:-unset}" >> "$PSQL_LOG"
case "\$*" in
    *information_schema*) echo t ;;
    *"FROM endpoint"*) printf '1\talice\tCN=alice\tAlice\tY\tN\tN\n' ;;
esac
exit 0
STUBEOF
    chmod +x "$STUB/psql"
}

teardown() {
    if [ -n "${TMP_CASE_DIR:-}" ]; then
        rm -rf -- "${TMP_CASE_DIR:?}"
    fi
    [ -n "${TT:-}" ] || return 0
    # Tests chmod folders to 000 or 500; restore access so the removal works.
    chmod -R u+rwx "$TT" 2>/dev/null || true
    rm -rf "$TT"
}

# A throwaway repository holding a copy of the real .gitignore, isolated from
# the developer's global git config, so the checks can fail on untracked paths.
ignore_repo() {
    [ -f "$REPO_GITIGNORE" ] || skip "no .gitignore next to the source tree"
    IGN="$TT/ignrepo"
    mkdir -p "$IGN"
    cp "$REPO_GITIGNORE" "$IGN/.gitignore"
    unset XDG_CONFIG_HOME GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
    export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
    git -C "$IGN" init -q
}

is_ignored() { git -C "$IGN" check-ignore -q --no-index "$1"; }

@test "generate-certs.sh writes to ~/.config/uudex/tls by default and not to the working directory" {
    cd "$WORKDIR"
    run "$GEN_SCRIPT" alice -k 2048
    [ "$status" -eq 0 ]
    for f in $ALL_FILES; do [ -s "$FAKE_HOME/.config/uudex/tls/$f" ]; done
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "generate-certs.sh honours UUDEX_CERTS and leaves the default location empty" {
    cd "$WORKDIR"
    UUDEX_CERTS="$TT/custom" run "$GEN_SCRIPT" alice -k 2048
    [ "$status" -eq 0 ]
    [ -s "$TT/custom/alice.key" ]
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
}

@test "generate-certs.sh -o writes to the given folder" {
    cd "$WORKDIR"
    run "$GEN_SCRIPT" alice -k 2048 -o "$TT/dash-o"
    [ "$status" -eq 0 ]
    [ -s "$TT/dash-o/alice.key" ]
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
}

@test "generate-certs.sh refuses when neither HOME nor UUDEX_CERTS nor -o is given" {
    cd "$WORKDIR"
    run env -u HOME -u UUDEX_CERTS "$GEN_SCRIPT" alice -k 2048
    [ "$status" -ne 0 ]
    [[ "$output" == *"UUDEX_CERTS"* ]]
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "generate-certs.sh --help and -o work with HOME unset" {
    cd "$WORKDIR"
    run env -u HOME -u UUDEX_CERTS "$GEN_SCRIPT" --help
    [ "$status" -eq 0 ]
    run env -u HOME -u UUDEX_CERTS "$GEN_SCRIPT" alice -k 2048 -o "$TT/nohome"
    [ "$status" -eq 0 ]
    [ -s "$TT/nohome/alice.key" ]
}

@test "generate-certs.sh creates the output folder with mode 700" {
    cd "$WORKDIR"
    run "$GEN_SCRIPT" alice -k 2048 -o "$TT/private"
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$TT/private")" = "700" ]
}

@test "generate-certs.sh refuses an output folder that group or others can write" {
    cd "$WORKDIR"
    for m in 775 757 777; do
        mkdir -p "$TT/shared$m"
        chmod "$m" "$TT/shared$m"
        run "$GEN_SCRIPT" alice -k 2048 -o "$TT/shared$m"
        [ "$status" -ne 0 ] || { echo "accepted mode $m"; return 1; }
        [[ "$output" == *"writable"* ]]
        [ -z "$(ls -A "$TT/shared$m")" ]
    done
}

@test "generate-certs.sh refuses an output folder owned by someone else" {
    [ ! -O /usr ] || skip "running as the owner of /usr"
    cd "$WORKDIR"
    run "$GEN_SCRIPT" alice -k 2048 -o /usr
    [ "$status" -ne 0 ]
    [[ "$output" == *"owned by you"* ]]
}

@test "help text no longer suggests /tmp for the output folder" {
    run "$GEN_SCRIPT" --help
    [[ "$output" != *"/tmp/certs"* ]]
    run "$PG_SCRIPT" --help
    [[ "$output" != *"/tmp/certs"* ]]
}

@test "postgres script help shows the home-based default output directory" {
    run "$PG_SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *'$HOME/.config/uudex/tls'* ]]
}

@test "postgres script refuses to run without a database password and never calls psql" {
    cd "$WORKDIR"
    PATH="$STUB:$PATH" run "$PG_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"DB_PASSWORD"* ]]
    [ ! -e "$PSQL_LOG" ]
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "postgres script has no literal default database password" {
    run /usr/bin/grep -nE 'DB_PASSWORD="\$\{DB_PASSWORD:-[^}]' "$PG_SCRIPT"
    [ "$status" -eq 1 ]
}

@test "postgres script accepts DB_PASSWORD from the environment and writes to the default folder" {
    cd "$WORKDIR"
    DB_PASSWORD=secret-from-env PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048
    [ "$status" -eq 0 ]
    [ -e "$PSQL_LOG" ]
    /usr/bin/grep -q 'PGPASSWORD=secret-from-env' "$PSQL_LOG"
    for f in $ALL_FILES; do [ -s "$FAKE_HOME/.config/uudex/tls/$f" ]; done
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "postgres script accepts --password" {
    cd "$WORKDIR"
    PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 --password secret-from-flag
    [ "$status" -eq 0 ]
    /usr/bin/grep -q 'PGPASSWORD=secret-from-flag' "$PSQL_LOG"
    [ -s "$FAKE_HOME/.config/uudex/tls/alice.key" ]
}

@test "postgres script honours UUDEX_CERTS" {
    cd "$WORKDIR"
    UUDEX_CERTS="$TT/custom" DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048
    [ "$status" -eq 0 ]
    [ -s "$TT/custom/alice.key" ]
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
}

@test "postgres script -o writes to the given folder" {
    cd "$WORKDIR"
    DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 -o "$TT/dash-o"
    [ "$status" -eq 0 ]
    [ -s "$TT/dash-o/alice.key" ]
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
}

@test "postgres script refuses without HOME, UUDEX_CERTS or -o, but --help and -o still work" {
    cd "$WORKDIR"
    DB_PASSWORD=x PATH="$STUB:$PATH" run env -u HOME -u UUDEX_CERTS "$PG_SCRIPT" --key-size 2048
    [ "$status" -ne 0 ]
    [[ "$output" == *"UUDEX_CERTS"* ]]
    [ -z "$(ls -A "$WORKDIR")" ]
    run env -u HOME -u UUDEX_CERTS "$PG_SCRIPT" --help
    [ "$status" -eq 0 ]
    DB_PASSWORD=x PATH="$STUB:$PATH" run env -u HOME -u UUDEX_CERTS "$PG_SCRIPT" --key-size 2048 -o "$TT/nohome"
    [ "$status" -eq 0 ]
    [ -s "$TT/nohome/alice.key" ]
}

@test "postgres script creates the output folder with mode 700" {
    cd "$WORKDIR"
    DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 -o "$TT/private"
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$TT/private")" = "700" ]
}

@test "postgres script refuses an output folder that group or others can write" {
    for m in 775 757 777; do
        mkdir -p "$TT/shared$m"
        chmod "$m" "$TT/shared$m"
        DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 -o "$TT/shared$m"
        [ "$status" -ne 0 ] || { echo "accepted mode $m"; return 1; }
        [[ "$output" == *"writable"* ]]
        [ -z "$(ls -A "$TT/shared$m")" ]
    done
}

@test "postgres script refuses an output folder owned by someone else" {
    [ ! -O /usr ] || skip "running as the owner of /usr"
    DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 -o /usr
    [ "$status" -ne 0 ]
    [[ "$output" == *"owned by you"* ]]
}

@test "gitignore ignores key and certificate files anywhere in the repository" {
    ignore_repo
    for p in infrastructure/certs/certs/ca.key infrastructure/certs/certs/x.crt infrastructure/certs/x.p12 \
             some.pem some.key tls/a.csr deep/er/dir/x.pfx; do
        is_ignored "$p" || { echo "not ignored: $p"; return 1; }
    done
}

@test "gitignore: each extension rule is needed (paths only one rule matches)" {
    ignore_repo
    for p in only.crt only.srl only.pfx only.csr only.pem only.p12; do
        is_ignored "$p" || { echo "not ignored: $p"; return 1; }
    done
}

@test "gitignore ignores the certs output folder at any depth" {
    ignore_repo
    is_ignored fastapi-web-server/certs/readme.txt
    is_ignored infrastructure/certs/certs/readme.txt
    is_ignored certs/readme.txt
}

@test "gitignore does not hide new files next to the scripts" {
    ignore_repo
    run is_ignored infrastructure/certs/new-helper.sh
    [ "$status" -ne 0 ]
    run is_ignored infrastructure/certs/tests/new.bats
    [ "$status" -ne 0 ]
}

# generate-certs.sh must fail loudly: non-zero status, a message naming the
# problem, no success line, and no key written.

assert_refused_without_files() {
    local dir="$1" needle="$2"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$needle"* ]]
    [[ "$output" != *"successfully"* ]]
    [ -z "$(ls -A "$dir" 2>/dev/null)" ]
}

# Replaces openssl with a stub that always fails. A run that reaches it has
# passed every argument check, so the check is observable without key generation.
fake_openssl_failing() {
    FAKEBIN="$TT/fakebin"
    mkdir -p "$FAKEBIN"
    printf '#!/bin/sh\nexit 1\n' > "$FAKEBIN/openssl"
    chmod +x "$FAKEBIN/openssl"
}

assert_passed_argument_checks() {
    [ "$status" -ne 0 ]
    [[ "$output" == *"step failed: generate CA key"* ]]
}

@test "generate-certs.sh rejects key sizes outside 2048 to 16384 and non-numbers, stating the range" {
    cd "$WORKDIR"
    fake_openssl_failing
    local i=0 v
    for v in 0 1024 2047 16385 20000 99999 100000 abc 20.48; do
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k "$v" -o "$TT/kv$i"
        echo "key size $v: $output"
        assert_refused_without_files "$TT/kv$i" "--key-size"
        [[ "$output" == *"2048 to 16384"* ]]
    done
}

@test "generate-certs.sh accepts the key size limits 2048 and 16384" {
    cd "$WORKDIR"
    fake_openssl_failing
    local v
    for v in 2048 16384; do
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k "$v" -o "$TT/ok$v"
        echo "limit $v: $output"
        assert_passed_argument_checks
    done
}

@test "generate-certs.sh rejects --days outside 1 to 999999 and non-numbers, stating the range" {
    cd "$WORKDIR"
    fake_openssl_failing
    local i=0 v
    for v in 0 1000000 9999999 abc 1.5; do
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d "$v" -o "$TT/d$i"
        echo "days $v: $output"
        assert_refused_without_files "$TT/d$i" "--days"
        [[ "$output" == *"1 to 999999"* ]]
    done
}

@test "generate-certs.sh accepts the --days limits 1 and 999999" {
    cd "$WORKDIR"
    fake_openssl_failing
    local v
    for v in 1 999999; do
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d "$v" -o "$TT/ok$v"
        echo "limit $v: $output"
        assert_passed_argument_checks
    done
}

@test "generate-certs.sh refuses full-width digits for --key-size and --days under a UTF-8 locale" {
    locale -a | /usr/bin/grep -qix 'en_US.utf-\?8' || skip "en_US.UTF-8 locale is not installed"
    cd "$WORKDIR"
    fake_openssl_failing
    local wide_key wide_days
    wide_key=$(printf '\357\274\222\357\274\220\357\274\224\357\274\230')
    wide_days=$(printf '\357\274\223')
    LC_ALL=en_US.UTF-8 PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k "$wide_key" -o "$TT/wk"
    assert_refused_without_files "$TT/wk" "--key-size"
    LC_ALL=en_US.UTF-8 PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d "$wide_days" -o "$TT/wd"
    assert_refused_without_files "$TT/wd" "--days"
}

@test "generate-certs.sh stops with a named step when openssl fails and leaves no files" {
    cd "$WORKDIR"
    fake_openssl_failing
    PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -o "$TT/failing"
    [ "$status" -ne 0 ]
    [[ "$output" == *"step failed: generate CA key"* ]]
    [[ "$output" != *"successfully"* ]]
    [ -z "$(ls -A "$TT/failing")" ]
}

@test "generate-certs.sh names the server key step, once, when only that openssl call fails" {
    cd "$WORKDIR"
    local real_openssl
    real_openssl=$(command -v openssl)
    mkdir -p "$TT/selective"
    printf '#!/bin/sh\ncase "$*" in *localhost.key*) exit 1 ;; esac\nexec %s "$@"\n' "$real_openssl" > "$TT/selective/openssl"
    chmod +x "$TT/selective/openssl"
    PATH="$TT/selective:$PATH" run --separate-stderr timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/srv"
    [ "$status" -ne 0 ]
    [[ "$stderr" == *"step failed: generate server key"* ]]
    [ "$(printf '%s\n' "$stderr" | /usr/bin/grep -c 'step failed')" -eq 1 ]
    [[ "$output" != *"Server certificate generated"* ]]
}

@test "generate-certs.sh reports a failed progress message under its own step, not 'starting up'" {
    [ -w /dev/full ] || skip "/dev/full is not available"
    cd "$WORKDIR"
    run bash -c '"$0" alice -k 2048 -o "$1" 2>&1 >/dev/full' "$GEN_SCRIPT" "$TT/full"
    [ "$status" -ne 0 ]
    [[ "$output" == *"step failed: print progress"* ]]
    [[ "$output" != *"starting up"* ]]
}

@test "generate-certs.sh reports one error when the folder permissions cannot be read" {
    cd "$WORKDIR"
    mkdir -p "$TT/faills"
    printf '#!/bin/sh\nexit 1\n' > "$TT/faills/ls"
    chmod +x "$TT/faills/ls"
    PATH="$TT/faills:$PATH" run --separate-stderr timeout 5 "$GEN_SCRIPT" alice -k 2048 -o "$TT/lsdir"
    [ "$status" -ne 0 ]
    [[ "$stderr" == *"$TT/lsdir"* ]]
    [ "$(printf '%s\n' "$stderr" | /usr/bin/grep -c .)" -eq 1 ]
}

@test "generate-certs.sh --list on a missing folder exits 1 with the reason on stderr and no step failure" {
    cd "$WORKDIR"
    run --separate-stderr timeout 5 "$GEN_SCRIPT" --list -o "$TT/nothere"
    [ "$status" -eq 1 ]
    [[ "$stderr" == *"does not exist"* ]]
    [[ "$stderr" != *"step failed"* ]]
    [[ "$output" != *"step failed"* ]]
    [ ! -e "$TT/nothere" ]
}

@test "generate-certs.sh refuses an existing owned folder it cannot write, naming it" {
    [ "$(id -u)" -ne 0 ] || skip "root can write to a mode 0500 folder"
    cd "$WORKDIR"
    mkdir -p "$TT/readonly"
    chmod 500 "$TT/readonly"
    run timeout 5 "$GEN_SCRIPT" alice -k 2048 -o "$TT/readonly"
    chmod 700 "$TT/readonly"
    assert_refused_without_files "$TT/readonly" "$TT/readonly"
    [[ "$output" == *"not writable"* ]]
}

@test "generate-certs.sh refuses each value option given last with no value" {
    cd "$WORKDIR"
    for opt in --domain -c --country -s --state -l --city -d --days -k --key-size -o --output-dir --org --ca-name --config; do
        run timeout 5 "$GEN_SCRIPT" alice "$opt"
        [ "$status" -ne 124 ] || { echo "$opt hung"; return 1; }
        [ "$status" -ne 0 ] || { echo "$opt accepted with no value"; return 1; }
        [[ "$output" == *"$opt requires a value"* ]] || { echo "$opt: $output"; return 1; }
    done
}

@test "generate-certs.sh refuses a value option followed by another option or an empty value" {
    cd "$WORKDIR"
    run timeout 5 "$GEN_SCRIPT" alice --domain --server-only -o "$TT/dd"
    [ "$status" -ne 0 ]
    [ "$status" -ne 124 ]
    [[ "$output" == *"--domain requires a value"* ]]
    run timeout 5 "$GEN_SCRIPT" alice -o -k 2048
    [ "$status" -ne 0 ]
    [ "$status" -ne 124 ]
    [[ "$output" == *"-o requires a value"* ]]
    run timeout 5 "$GEN_SCRIPT" alice -s "" -o "$TT/empty"
    [ "$status" -ne 0 ]
    [[ "$output" == *"-s requires a value"* ]]
    [ ! -e "$TT/empty" ]
    run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d -5 -o "$TT/negdays"
    [ "$status" -ne 0 ]
    [[ "$output" == *"-d requires a value, got the option-like '-5'"* ]]
    [ ! -e "$TT/negdays" ]
}

@test "generate-certs.sh refuses a blank value for each value option and writes nothing" {
    cd "$WORKDIR"
    fake_openssl_failing
    local opt blank
    for opt in --domain -c -s -l -d -k -o --org --ca-name --config; do
        for blank in " " "   " "$(printf '\t')"; do
            PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice "$opt" "$blank"
            [ "$status" -ne 0 ] || { echo "$opt accepted a blank value"; return 1; }
            [[ "$output" == *"$opt requires a value"* ]] || { echo "$opt: $output"; return 1; }
            [[ "$output" != *"step failed"* ]] || { echo "$opt: $output"; return 1; }
        done
    done
    [ -z "$(ls -A "$WORKDIR")" ]
}

# Config file defaults. Subjects are read back from the certificates the
# script wrote, not from its output.

EXAMPLE_CONF="$SCRIPTS/uudex-certs.conf.example"

subject_of() { openssl x509 -in "$1" -noout -subject -nameopt RFC2253; }

write_conf() {
    CONF="$TT/test.conf"
    printf '%s\n' "$@" > "$CONF"
    chmod 600 "$CONF"
}

FULL_CONF=(
    "C = CA" "ST = Ontario" "L = Toronto" "O = Conf Org" "CA_CN = Conf CA"
    "KEY_SIZE = 2048" "DAYS = 30" "DOMAINS = conf.example, 10.1.2.3"
)

@test "config: built-in defaults apply with no config file" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/o"
    [ "$status" -eq 0 ]
    [ "$(subject_of "$TT/o/ca.crt")" = "subject=CN=LocalCA,O=Organization,L=City,ST=State,C=US" ]
}

@test "config: a partial config sets its own keys and the rest stay built-in" {
    cd "$WORKDIR"
    write_conf "O = Partial Org"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 --config "$CONF" -o "$TT/o"
    [ "$status" -eq 0 ]
    [ "$(subject_of "$TT/o/ca.crt")" = "subject=CN=LocalCA,O=Partial Org,L=City,ST=State,C=US" ]
}

@test "config: values from the config are used when no option is given" {
    cd "$WORKDIR"
    write_conf "${FULL_CONF[@]}" "OUTPUT_DIR = $TT/cfgout"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -eq 0 ]
    local d="$TT/cfgout"
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
    [ "$(subject_of "$d/ca.crt")" = "subject=CN=Conf CA,O=Conf Org,L=Toronto,ST=Ontario,C=CA" ]
    [ "$(subject_of "$d/alice.crt")" = "subject=CN=alice,O=Conf Org,L=Toronto,ST=Ontario,C=CA" ]
    [ "$(subject_of "$d/server.crt")" = "subject=CN=conf.example,O=Conf Org,L=Toronto,ST=Ontario,C=CA" ]
    openssl x509 -in "$d/server.crt" -noout -ext subjectAltName | /usr/bin/grep -q 'DNS:conf.example'
    openssl x509 -in "$d/server.crt" -noout -ext subjectAltName | /usr/bin/grep -q 'IP Address:10.1.2.3'
    openssl x509 -in "$d/alice.crt" -noout -text | /usr/bin/grep -q 'Public-Key: (2048 bit)'
    openssl x509 -in "$d/alice.crt" -noout -checkend $((29 * 86400))
    run openssl x509 -in "$d/alice.crt" -noout -checkend $((31 * 86400))
    [ "$status" -ne 0 ]
}

@test "config: the default path is read when it exists" {
    cd "$WORKDIR"
    mkdir -p "$FAKE_HOME/.config/uudex"
    write_conf "O = Default Path Org"
    cp "$CONF" "$FAKE_HOME/.config/uudex/certs.conf"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048
    [ "$status" -eq 0 ]
    [[ "$(subject_of "$FAKE_HOME/.config/uudex/tls/ca.crt")" == *"O=Default Path Org"* ]]
}

@test "config: UUDEX_CERTS_CONF points at another file" {
    cd "$WORKDIR"
    write_conf "O = Env Conf Org"
    UUDEX_CERTS_CONF="$CONF" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/o"
    [ "$status" -eq 0 ]
    [[ "$(subject_of "$TT/o/ca.crt")" == *"O=Env Conf Org"* ]]
}

@test "config: every option overrides the config value" {
    cd "$WORKDIR"
    write_conf "${FULL_CONF[@]}" "OUTPUT_DIR = $TT/cfgout"
    sed -i 's/^KEY_SIZE = 2048/KEY_SIZE = 2560/' "$CONF"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -c US -s Washington -l Richland \
        --org "Opt Org" --ca-name "Opt CA" -k 2048 -d 400 --domain opt.example -o "$TT/optout"
    [ "$status" -eq 0 ]
    local d="$TT/optout"
    [ ! -e "$TT/cfgout" ]
    [ "$(subject_of "$d/ca.crt")" = "subject=CN=Opt CA,O=Opt Org,L=Richland,ST=Washington,C=US" ]
    [ "$(subject_of "$d/alice.crt")" = "subject=CN=alice,O=Opt Org,L=Richland,ST=Washington,C=US" ]
    [ "$(subject_of "$d/server.crt")" = "subject=CN=opt.example,O=Opt Org,L=Richland,ST=Washington,C=US" ]
    run openssl x509 -in "$d/server.crt" -noout -ext subjectAltName
    [ "$status" -eq 0 ]
    [[ "$output" == *"DNS:opt.example"* ]]
    [[ "$output" != *"conf.example"* ]]
    [[ "$output" != *"10.1.2.3"* ]]
    openssl x509 -in "$d/alice.crt" -noout -text | /usr/bin/grep -q 'Public-Key: (2048 bit)'
    openssl x509 -in "$d/alice.crt" -noout -checkend $((399 * 86400))
}

@test "config: UUDEX_CERTS beats OUTPUT_DIR in the config" {
    cd "$WORKDIR"
    write_conf "OUTPUT_DIR = $TT/cfgout" "KEY_SIZE = 2048"
    UUDEX_CERTS="$TT/envout" run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -eq 0 ]
    [ -s "$TT/envout/alice.key" ]
    [ ! -e "$TT/cfgout" ]
}

@test "config: OUTPUT_DIR may start with ~/ and must otherwise be absolute" {
    cd "$WORKDIR"
    write_conf "OUTPUT_DIR = ~/from-conf" "KEY_SIZE = 2048"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -eq 0 ]
    [ -s "$FAKE_HOME/from-conf/alice.key" ]
    write_conf "OUTPUT_DIR = relative/dir"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 1"* && "$output" == *"OUTPUT_DIR must be an absolute path"* ]]
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "config: an unknown key is refused naming the line and the key" {
    cd "$WORKDIR"
    write_conf "# comment" "" "C = US" "COUNTY = Benton"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$CONF line 4: unknown key 'COUNTY'"* ]]
    [[ "$output" != *"successfully"* ]]
    [ ! -e "$TT/o" ]
}

@test "config: a malformed line, a duplicate key and CRLF endings are refused naming the line" {
    cd "$WORKDIR"
    write_conf "C = US" "this is not a setting"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: expected KEY = VALUE"* ]]
    write_conf "C = US" "C = CA"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: key 'C' is set twice"* ]]
    printf 'C = US\r\n' > "$CONF"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 1: carriage return"* ]]
    [ ! -e "$TT/o" ]
}

@test "config: bad KEY_SIZE and DAYS fail with the same range message and the line, even when overridden" {
    cd "$WORKDIR"
    write_conf "C = US" "KEY_SIZE = 1024"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: KEY_SIZE must be a whole number from 2048 to 16384, got '1024'"* ]]
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -k 2048 -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: KEY_SIZE"* ]]
    write_conf "DAYS = 1.5"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 1: DAYS must be a whole number from 1 to 999999, got '1.5'"* ]]
    [ ! -e "$TT/o" ]
}

@test "config: a blank, option-like or empty-item value is refused like the option form" {
    cd "$WORKDIR"
    local bad
    for bad in "ST =" "ST = -x" "DOMAINS = a.example,,b.example" "DOMAINS = a.example," "O = -"; do
        write_conf "$bad"
        run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
        [ "$status" -ne 0 ] || { echo "accepted: $bad"; return 1; }
        [[ "$output" == *"line 1"* && "$output" == *"requires a value"* ]] || { echo "$bad: $output"; return 1; }
    done
    [ ! -e "$TT/o" ]
}

@test "config: an explicit config that does not exist is refused, a missing default is fine" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" alice --config "$TT/nothere.conf" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"nothere.conf does not exist"* ]]
    UUDEX_CERTS_CONF="$TT/nothere.conf" run timeout 60 "$GEN_SCRIPT" alice -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"does not exist"* ]]
    [ ! -e "$TT/o" ]
    [ ! -e "$FAKE_HOME/.config/uudex/certs.conf" ]
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/o"
    [ "$status" -eq 0 ]
}

@test "config: a directory, or a file others can write, is refused and nothing is written" {
    cd "$WORKDIR"
    mkdir "$TT/dir.conf"
    run timeout 60 "$GEN_SCRIPT" alice --config "$TT/dir.conf" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"is not a regular file"* ]]
    write_conf "C = US"
    chmod 666 "$CONF"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"writable by other users"* ]]
    [ ! -e "$TT/o" ]
}

@test "config: a file that only the group, or only others, can write is refused and nothing is written" {
    cd "$WORKDIR"
    local m
    for m in 620 602; do
        write_conf "C = US"
        chmod "$m" "$CONF"
        run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$TT/o$m"
        [ "$status" -ne 0 ] || { echo "accepted mode $m"; return 1; }
        [[ "$output" == *"writable by other users"* ]] || { echo "mode $m: $output"; return 1; }
        [ ! -e "$TT/o$m" ]
    done
}

@test "config: a file owned by someone else is refused for ownership before its content is read" {
    local other=/etc/hostname
    [ -f "$other" ] && [ -r "$other" ] && [ ! -O "$other" ] || skip "$other is not a readable file owned by another user"
    [ ! -w "$other" ] || skip "$other is writable by this user"
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" alice --config "$other" -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"must be readable and owned by you"* ]]
    [[ "$output" != *"expected KEY = VALUE"* ]]
    [ ! -e "$TT/o" ]
}

@test "config: shell syntax in a value is refused, never run, and nothing is written" {
    cd "$WORKDIR"
    write_conf 'C=$(touch '"$TT"'/pwned)'
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -k 2048 -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 1: C contains the character"* ]]
    [ ! -e "$TT/pwned" ]
    [ ! -e "$TT/o" ]
}

@test "config: with every value in the config, a client name alone makes the CA, server and client certificates" {
    cd "$WORKDIR"
    write_conf "${FULL_CONF[@]}"
    cp "$CONF" "$TT/keep.conf"
    mkdir -p "$FAKE_HOME/.config/uudex"
    cp "$CONF" "$FAKE_HOME/.config/uudex/certs.conf"
    run timeout 60 "$GEN_SCRIPT" alice
    [ "$status" -eq 0 ]
    local d="$FAKE_HOME/.config/uudex/tls"
    for f in ca.crt ca.key server.crt server.key alice.crt alice.key alice.p12; do [ -s "$d/$f" ]; done
    openssl verify -CAfile "$d/ca.crt" "$d/server.crt" "$d/alice.crt"
}

@test "config: the shipped example makes certificates with the values of the example certificates" {
    cd "$WORKDIR"
    [ -f "$EXAMPLE_CONF" ]
    mkdir -p "$FAKE_HOME/.config/uudex"
    cp "$EXAMPLE_CONF" "$FAKE_HOME/.config/uudex/certs.conf"
    chmod 600 "$FAKE_HOME/.config/uudex/certs.conf"
    run timeout 60 "$GEN_SCRIPT" alice
    [ "$status" -eq 0 ]
    local d="$FAKE_HOME/.config/uudex/tls"
    [ "$(subject_of "$d/ca.crt")" = "subject=CN=UUDEX CA,O=UUDEX CA,L=Richland,ST=Washington,C=US" ]
    openssl x509 -in "$d/localhost.crt" -noout -text 2>/dev/null | /usr/bin/grep -q 'Public-Key: (2048 bit)' \
        || openssl x509 -in "$d/server.crt" -noout -text | /usr/bin/grep -q 'Public-Key: (2048 bit)'
    openssl x509 -in "$d/server.crt" -noout -ext subjectAltName | /usr/bin/grep -q 'IP Address:127.0.0.1'
    run /usr/bin/grep -qi 'raven2' "$EXAMPLE_CONF"
    [ "$status" -eq 1 ]
}

@test "config: --list uses OUTPUT_DIR from the config" {
    cd "$WORKDIR"
    write_conf "OUTPUT_DIR = $TT/listdir" "KEY_SIZE = 2048"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -eq 0 ]
    run timeout 60 "$GEN_SCRIPT" --list --config "$CONF"
    [ "$status" -eq 0 ]
    [[ "$output" == *"$TT/listdir"* && "$output" == *"Name: alice"* ]]
}

@test "config: --config beats UUDEX_CERTS_CONF, even when that variable is empty" {
    cd "$WORKDIR"
    write_conf "O = Flag Org" "KEY_SIZE = 2048"
    local flag_conf="$CONF"
    printf 'O = Env Org\nKEY_SIZE = 2048\n' > "$TT/env.conf"
    chmod 600 "$TT/env.conf"
    UUDEX_CERTS_CONF="$TT/env.conf" run timeout 60 "$GEN_SCRIPT" alice --config "$flag_conf" -o "$TT/o"
    [ "$status" -eq 0 ]
    [[ "$(subject_of "$TT/o/ca.crt")" == *"O=Flag Org"* ]]
    UUDEX_CERTS_CONF="" run timeout 60 "$GEN_SCRIPT" alice --config "$flag_conf" -o "$TT/o2"
    [ "$status" -eq 0 ]
    [[ "$(subject_of "$TT/o2/ca.crt")" == *"O=Flag Org"* ]]
}

@test "config: an empty UUDEX_CERTS_CONF is refused with a message and nothing is written" {
    cd "$WORKDIR"
    UUDEX_CERTS_CONF="" run timeout 60 "$GEN_SCRIPT" alice -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"UUDEX_CERTS_CONF requires a value"* ]]
    [ ! -e "$TT/o" ]
}

@test "config: OUTPUT_DIR with ~/ is refused naming the line when HOME is not set" {
    cd "$WORKDIR"
    write_conf "C = US" "OUTPUT_DIR = ~/from-conf" "KEY_SIZE = 2048"
    run env -u HOME -u UUDEX_CERTS timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: OUTPUT_DIR uses ~ but HOME is not set"* ]]
    [ -z "$(ls -A "$WORKDIR")" ]
    [ ! -e "$FAKE_HOME/from-conf" ]
}

@test "help text says what OUTPUT_DIR does and where it ranks" {
    run "$GEN_SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"OUTPUT_DIR sets the output directory when -o and UUDEX_CERTS are not given"* ]]
    [[ "$output" == *"overrides UUDEX_CERTS and OUTPUT_DIR"* ]]
}

# Subject values reach openssl -subj and a generated openssl config, so a
# character that reads as syntax is refused. Nothing may be written.

SUBJECT_BAD_CHARS=("/" "\\" "#" "\$" "\"" "'" "+")

ORG_LABEL="ORG (second argument or --org)"

cli_label() { if [ "$1" = --org ]; then echo "$ORG_LABEL"; else echo "$1"; fi; }

assert_subject_refused() {
    local label="$1" ch="$2" outdir="$3"
    [ "$status" -ne 0 ] || { echo "accepted '$ch' in $label"; return 1; }
    [[ "$output" == *"$label contains the character '$ch'"* ]] || { echo "$label '$ch': $output"; return 1; }
    [[ "$output" != *"step failed"* ]] || { echo "$label '$ch' got past the checks: $output"; return 1; }
    [ ! -e "$outdir" ] || { echo "$label '$ch' wrote $outdir"; return 1; }
}

@test "subject values: each character openssl would misread is refused on the command line, writing nothing" {
    cd "$WORKDIR"
    fake_openssl_failing
    local ch opt i=0
    for ch in "${SUBJECT_BAD_CHARS[@]}"; do
        for opt in --country --state --city --org --ca-name; do
            i=$((i + 1))
            PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 "$opt" "a${ch}b" -o "$TT/s$i"
            assert_subject_refused "$(cli_label "$opt")" "$ch" "$TT/s$i"
        done
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice "a${ch}b" -k 2048 -o "$TT/s$i"
        assert_subject_refused "$ORG_LABEL" "$ch" "$TT/s$i"
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" "a${ch}b" -k 2048 -o "$TT/s$i"
        assert_subject_refused "CLIENT_NAME" "$ch" "$TT/s$i"
    done
    [ -z "$(ls -A "$WORKDIR")" ]
    [ ! -e "$FAKE_HOME/.config" ]
}

@test "subject values: a control character is refused on the command line and in the config, writing nothing" {
    cd "$WORKDIR"
    fake_openssl_failing
    local i=0 opt key
    for opt in --country --state --city --org --ca-name; do
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 "$opt" $'a\nb' -o "$TT/n$i"
        [ "$status" -ne 0 ] || { echo "accepted a newline in $opt"; return 1; }
        [[ "$output" == *"$(cli_label "$opt") contains a control character"* ]] || { echo "$opt: $output"; return 1; }
        [ ! -e "$TT/n$i" ]
    done
    for key in C ST L O CA_CN; do
        i=$((i + 1))
        write_conf "$key = a"$'\t'"b"
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 --config "$CONF" -o "$TT/n$i"
        [ "$status" -ne 0 ] || { echo "accepted a tab in $key"; return 1; }
        [[ "$output" == *"$CONF line 1: $key contains a control character"* ]] || { echo "$key: $output"; return 1; }
        [ ! -e "$TT/n$i" ]
    done
}

@test "subject values: each character openssl would misread is refused in the config, naming the line, writing nothing" {
    cd "$WORKDIR"
    fake_openssl_failing
    local ch key i=0
    for ch in "${SUBJECT_BAD_CHARS[@]}"; do
        for key in C ST L O CA_CN; do
            i=$((i + 1))
            write_conf "# header" "$key = a${ch}b"
            PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 --config "$CONF" -o "$TT/c$i"
            assert_subject_refused "$CONF line 2: $key" "$ch" "$TT/c$i"
        done
    done
    [ -z "$(ls -A "$WORKDIR")" ]
    [ ! -e "$FAKE_HOME/.config" ]
}

@test "subject values: an inline comment, an injected field and an environment reference in the config are refused" {
    cd "$WORKDIR"
    fake_openssl_failing
    local i=0 line
    for line in "L = Richland # city" "O = Acme/CN=evil.example/O=Injected" "O = \${ENV::HOME}"; do
        i=$((i + 1))
        write_conf "$line"
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 --config "$CONF" -o "$TT/i$i"
        [ "$status" -ne 0 ] || { echo "accepted: $line"; return 1; }
        [[ "$output" == *"$CONF line 1:"* && "$output" == *"contains the character"* ]] || { echo "$line: $output"; return 1; }
        [ ! -e "$TT/i$i" ]
    done
}

# Values are built with printf escapes so this file stays ASCII: an accented
# letter, and a byte that is not valid UTF-8.
assert_non_ascii_refused() {
    local locale="$1" i=0 opt key v
    fake_openssl_failing
    for v in "$(printf 'Caf\303\251')" "$(printf 'a\377b')"; do
        for opt in --country --state --city --org --ca-name; do
            i=$((i + 1))
            LC_ALL="$locale" PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 "$opt" "$v" -o "$TT/a$i"
            [ "$status" -ne 0 ] || { echo "accepted a non-ASCII value in $opt"; return 1; }
            [[ "$output" == *"$(cli_label "$opt") contains a non-ASCII character"* ]] || { echo "$opt: $output"; return 1; }
            [[ "$output" != *"step failed"* ]] || { echo "$opt got past the checks: $output"; return 1; }
            [ ! -e "$TT/a$i" ]
        done
        i=$((i + 1))
        LC_ALL="$locale" PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice "$v" -k 2048 -o "$TT/a$i"
        [[ "$status" -ne 0 && "$output" == *"$ORG_LABEL contains a non-ASCII character"* ]] || { echo "ORG: $output"; return 1; }
        [ ! -e "$TT/a$i" ]
        i=$((i + 1))
        LC_ALL="$locale" PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" "$v" -k 2048 -o "$TT/a$i"
        [[ "$status" -ne 0 && "$output" == *"CLIENT_NAME contains a non-ASCII character"* ]] || { echo "CLIENT_NAME: $output"; return 1; }
        [ ! -e "$TT/a$i" ]
        for key in C ST L O CA_CN; do
            i=$((i + 1))
            write_conf "$key = $v"
            LC_ALL="$locale" PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 --config "$CONF" -o "$TT/a$i"
            [ "$status" -ne 0 ] || { echo "accepted a non-ASCII value in $key"; return 1; }
            [[ "$output" == *"$CONF line 1: $key contains a non-ASCII character"* ]] || { echo "$key: $output"; return 1; }
            [ ! -e "$TT/a$i" ]
        done
        i=$((i + 1))
        LC_ALL="$locale" PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 --domain "$v" -o "$TT/a$i"
        [ "$status" -ne 0 ] || { echo "accepted a non-ASCII server name"; return 1; }
        [ ! -e "$TT/a$i" ]
    done
}

@test "subject values: a non-ASCII value is refused on the command line and in the config, writing nothing (C locale)" {
    cd "$WORKDIR"
    assert_non_ascii_refused C
}

@test "subject values: a non-ASCII value is refused the same way under a UTF-8 locale" {
    locale -a | /usr/bin/grep -qix 'en_US.utf-\?8' || skip "en_US.UTF-8 locale is not installed"
    cd "$WORKDIR"
    assert_non_ascii_refused en_US.UTF-8
}

@test "subject values: leading or trailing whitespace is refused on the command line, writing nothing" {
    cd "$WORKDIR"
    fake_openssl_failing
    local v opt i=0
    for v in " Acme" "Acme " " Acme "; do
        for opt in --country --state --city --org --ca-name; do
            i=$((i + 1))
            PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 "$opt" "$v" -o "$TT/w$i"
            [ "$status" -ne 0 ] || { echo "accepted '$v' in $opt"; return 1; }
            [[ "$output" == *"$(cli_label "$opt") has leading or trailing whitespace"* ]] || { echo "$opt '$v': $output"; return 1; }
            [[ "$output" != *"step failed"* ]] || { echo "$opt '$v' got past the checks: $output"; return 1; }
            [ ! -e "$TT/w$i" ]
        done
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice "$v" -k 2048 -o "$TT/w$i"
        [ "$status" -ne 0 ] || { echo "accepted '$v' as ORG"; return 1; }
        [[ "$output" == *"$ORG_LABEL has leading or trailing whitespace"* ]] || { echo "ORG '$v': $output"; return 1; }
        [ ! -e "$TT/w$i" ]
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" "$v" -k 2048 -o "$TT/w$i"
        [ "$status" -ne 0 ] || { echo "accepted '$v' as CLIENT_NAME"; return 1; }
        [[ "$output" == *"CLIENT_NAME has leading or trailing whitespace"* ]] || { echo "CLIENT_NAME '$v': $output"; return 1; }
        [ ! -e "$TT/w$i" ]
    done
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "subject values: the config trims edge whitespace, so all three certificates carry the same value" {
    cd "$WORKDIR"
    write_conf "O =    Acme   " "KEY_SIZE = 2048"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" --domain host.example -o "$TT/o"
    [ "$status" -eq 0 ]
    local f
    for f in ca alice server; do
        [[ "$(subject_of "$TT/o/$f.crt")" == *",O=Acme,"* ]] || { echo "$f: $(subject_of "$TT/o/$f.crt")"; return 1; }
    done
}

@test "subject values: = , ; & % : @ ( ) [ ] and spaces are allowed and read back the same from every certificate" {
    cd "$WORKDIR"
    write_conf "O = R&D, Inc. (West) = 100% ok; a:b @c [d]" "KEY_SIZE = 2048"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" --domain host.example -o "$TT/o"
    [ "$status" -eq 0 ]
    local want='O=R&D\, Inc. (West) = 100% ok\; a:b @c [d],'
    local f
    for f in ca alice server; do
        [[ "$(subject_of "$TT/o/$f.crt")" == *"$want"* ]] || { echo "$f: $(subject_of "$TT/o/$f.crt")"; return 1; }
    done
}

@test "existing CA: a different requested CA subject warns on stderr, the summary shows the CA in use, and the CA is not changed" {
    cd "$WORKDIR"
    local d="$TT/o" before
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --ca-name FirstCA --org FirstOrg
    [ "$status" -eq 0 ]
    [[ "$output" == *"CA subject: CN=FirstCA, O=FirstOrg, L=City, ST=State, C=US"* ]]
    before=$(cksum < "$d/ca.crt")
    run --separate-stderr timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" --ca-name SecondCA --org SecondOrg
    [ "$status" -eq 0 ]
    [[ "$stderr" == *"Warning:"* ]]
    [[ "$stderr" == *"CN=FirstCA, O=FirstOrg, L=City, ST=State, C=US"* ]]
    [[ "$stderr" == *"CN=SecondCA, O=SecondOrg, L=City, ST=State, C=US"* ]]
    [[ "$output" == *"CA subject: CN=FirstCA, O=FirstOrg, L=City, ST=State, C=US"* ]]
    [[ "$output" != *"CN=SecondCA"* ]]
    [ "$(cksum < "$d/ca.crt")" = "$before" ]
    [ "$(subject_of "$d/ca.crt")" = "subject=CN=FirstCA,O=FirstOrg,L=City,ST=State,C=US" ]
}

@test "existing CA: the same requested subject, or a new CA, prints no warning" {
    cd "$WORKDIR"
    local d="$TT/o"
    run --separate-stderr timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --ca-name FirstCA --org FirstOrg
    [ "$status" -eq 0 ]
    [[ "$stderr" != *"Warning"* ]]
    run --separate-stderr timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" --ca-name FirstCA --org FirstOrg
    [ "$status" -eq 0 ]
    [[ "$output" == *"Using existing CA certificate"* ]]
    [[ "$stderr" != *"Warning"* ]]
}

# Server names: checked before anything is written.

@test "domains: two DNS names and two IPv4 addresses in one run all land, numbered without gaps" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/o" \
        --domain a.example --domain b.example --domain 10.0.0.1 --domain 10.0.0.2
    [ "$status" -eq 0 ]
    run openssl x509 -in "$TT/o/server.crt" -noout -ext subjectAltName
    [ "$status" -eq 0 ]
    [[ "$output" == *"DNS:a.example, DNS:b.example, IP Address:10.0.0.1, IP Address:10.0.0.2"* ]]
}

@test "domains: an IPv6 address becomes an IP entry, not a DNS name" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/o" --domain host.example --domain ::1
    [ "$status" -eq 0 ]
    run openssl x509 -in "$TT/o/server.crt" -noout -ext subjectAltName
    [[ "$output" == *"DNS:host.example, IP Address:0:0:0:0:0:0:0:1"* ]]
    [[ "$output" != *"DNS:::1"* ]]
}

@test "domains: a bad name or address is refused before ca.key exists, from the option and from the config" {
    cd "$WORKDIR"
    fake_openssl_failing
    local i=0 bad
    for bad in 999.1.1.1 010.0.0.1 1.2.3.4/24 "foo bar" ::: 1:2:3:4:5:6:7:8: g::1 1:2:3:4:5:6:7::8 1:2:3 12345::1 "a\$b" "a\"b"; do
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/d$i" --domain "$bad"
        [ "$status" -ne 0 ] || { echo "accepted --domain $bad"; return 1; }
        [[ "$output" == *"--domain '$bad' is not a"* ]] || { echo "--domain $bad: $output"; return 1; }
        [[ "$output" != *"step failed"* ]] || { echo "--domain $bad got past the checks: $output"; return 1; }
        [ ! -e "$TT/d$i/ca.key" ]
        [ ! -e "$TT/d$i" ]
        write_conf "DOMAINS = ok.example, $bad"
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/e$i" --config "$CONF"
        [ "$status" -ne 0 ] || { echo "accepted DOMAINS $bad"; return 1; }
        [[ "$output" == *"$CONF line 1: DOMAINS '$bad' is not a"* ]] || { echo "DOMAINS $bad: $output"; return 1; }
        [ ! -e "$TT/e$i" ]
    done
}

@test "domains: a newline inside an IPv6-looking name is refused and no extra SAN entry is made" {
    cd "$WORKDIR"
    fake_openssl_failing
    PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/nl" \
        --domain host.example --domain $'::1\nDNS.9 = evil.example'
    [ "$status" -ne 0 ]
    [[ "$output" == *"is not a valid IPv6 address"* ]]
    [[ "$output" != *"step failed"* ]]
    [ ! -e "$TT/nl" ]
}

@test "domains: malformed DNS names and digit-and-dot names are refused before ca.key exists, from the option and from the config" {
    cd "$WORKDIR"
    fake_openssl_failing
    local label64 i=0 c bad want
    label64=$(printf '%064d' 0 | tr 0 a)
    [ "${#label64}" -eq 64 ]
    for c in "1.2.3|is not a valid IPv4 address" "1234.1.1.1|is not a valid IPv4 address" \
             "1.2.3.4.5|is not a valid IPv4 address" "123|is not a valid IPv4 address" \
             "..|an empty label" ".example|an empty label" "foo..example|an empty label" "example.|an empty label" \
             "foo.-bar.example|starts or ends with '-'" "a-.example|starts or ends with '-'" "foo.bar-|starts or ends with '-'" \
             "a*.example|'*' may only be the whole first label" "*a.example|'*' may only be the whole first label" \
             "foo.*.example|'*' may only be the whole first label" "*.*.example|'*' may only be the whole first label" \
             "foo.example.*|'*' may only be the whole first label" \
             "$label64.example|longer than 63 characters"; do
        bad="${c%%|*}" want="${c#*|}"
        i=$((i + 1))
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/n$i" --domain "$bad"
        [ "$status" -ne 0 ] || { echo "accepted --domain $bad"; return 1; }
        [[ "$output" == *"--domain '$bad' "*"$want"* ]] || { echo "--domain $bad: $output"; return 1; }
        [[ "$output" != *"step failed"* ]] || { echo "--domain $bad got past the checks: $output"; return 1; }
        [ ! -e "$TT/n$i/ca.key" ]
        [ ! -e "$TT/n$i" ]
        write_conf "DOMAINS = ok.example, $bad"
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/m$i" --config "$CONF"
        [ "$status" -ne 0 ] || { echo "accepted DOMAINS $bad"; return 1; }
        [[ "$output" == *"$CONF line 1: DOMAINS '$bad' "*"$want"* ]] || { echo "DOMAINS $bad: $output"; return 1; }
        [ ! -e "$TT/m$i" ]
    done
}

@test "domains: a first name over 64 characters is refused before any key is written, a longer later name is accepted" {
    cd "$WORKDIR"
    fake_openssl_failing
    local long64 long65 label63
    long64="$(printf '%040d' 0 | tr 0 a).$(printf '%023d' 0 | tr 0 b)"
    long65="$(printf '%040d' 0 | tr 0 a).$(printf '%024d' 0 | tr 0 b)"
    label63=$(printf '%063d' 0 | tr 0 a)
    [ "${#long64}" -eq 64 ]
    [ "${#long65}" -eq 65 ]
    PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/l1" --domain "$long65" --domain ok.example
    [ "$status" -ne 0 ]
    [[ "$output" == *"the first server name '$long65' is 65 characters"* ]]
    [[ "$output" != *"step failed"* ]]
    [ ! -e "$TT/l1" ]
    write_conf "DOMAINS = $long65, ok.example"
    PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/l2" --config "$CONF"
    [ "$status" -ne 0 ]
    [[ "$output" == *"the first server name '$long65' is 65 characters"* ]]
    [ ! -e "$TT/l2" ]
    PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/l3" --domain "$long64"
    assert_passed_argument_checks
    PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/l4" --domain ok.example --domain "$long65.$label63"
    assert_passed_argument_checks
}

@test "domains: valid names and addresses are accepted, including a wildcard, 0.0.0.0 and 255.255.255.255" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$TT/o" \
        --domain '*.example.com' --domain my_host-1.example --domain 0.0.0.0 --domain 255.255.255.255 --domain fe80::1
    [ "$status" -eq 0 ]
    run openssl x509 -in "$TT/o/server.crt" -noout -ext subjectAltName
    [[ "$output" == *"DNS:*.example.com, DNS:my_host-1.example, IP Address:0.0.0.0, IP Address:255.255.255.255, IP Address:FE80:0:0:0:0:0:0:1"* ]]
}

# Existing files, symlinks, half-made CAs and unsafe parents: refused before
# any key is made, and a refused run changes nothing.

# One line per entry, dotfiles included: a content hash for a regular file,
# a marker for anything else, so a rename, a new file or a link shows up.
snapshot() {
    local f
    shopt -s nullglob dotglob
    for f in "$1"/*; do
        if [ -f "$f" ] && [ ! -L "$f" ]; then
            printf '%s %s\n' "$(sha256sum < "$f" | cut -c1-64)" "${f##*/}"
        else
            printf 'other %s\n' "${f##*/}"
        fi
    done
    shopt -u nullglob dotglob
}

# An openssl that records each call and then runs the real one.
spy_openssl() {
    local real
    real=$(command -v openssl)
    SPYBIN="$TT/spybin"
    SPYLOG="$TT/openssl.calls"
    mkdir -p "$SPYBIN"
    : > "$SPYLOG"
    printf '#!/bin/sh\necho "$*" >> "%s"\nexec %s "$@"\n' "$SPYLOG" "$real" > "$SPYBIN/openssl"
    chmod +x "$SPYBIN/openssl"
}

make_full_set() {
    run timeout 60 "$GEN_SCRIPT" "${2:-alice}" -k 2048 -o "$1"
    [ "$status" -eq 0 ]
}

# Runs the script on an existing folder and checks the refusal: non-zero,
# the message names the needle, openssl was never called, and the folder is
# exactly as it was.
assert_refusal_changes_nothing() {
    local dir="$1" needle="$2" before
    shift 2
    before=$(snapshot "$dir")
    spy_openssl
    PATH="$SPYBIN:$PATH" run timeout 60 "$GEN_SCRIPT" "$@" -k 2048 -o "$dir"
    [ "$status" -ne 0 ] || { echo "accepted: $*"; return 1; }
    [[ "$output" == *"$needle"* ]] || { echo "message lacks '$needle': $output"; return 1; }
    [[ "$output" != *"successfully"* ]]
    [ ! -s "$SPYLOG" ] || { echo "openssl was called: $(cat "$SPYLOG")"; return 1; }
    [ "$(snapshot "$dir")" = "$before" ]
}

@test "existing files: a client that already has a key, certificate or bundle is refused, naming the file, and nothing changes" {
    cd "$WORKDIR"
    local d="$TT/o" ext other
    make_full_set "$d"
    assert_refusal_changes_nothing "$d" "$d/alice.key already exists" alice
    for ext in key crt p12; do
        rm -rf -- "${d:?}"
        make_full_set "$d"
        for other in key crt p12; do
            [ "$other" = "$ext" ] || rm -- "${d:?}/alice.${other:?}"
        done
        assert_refusal_changes_nothing "$d" "$d/alice.$ext already exists" alice
    done
}

@test "existing files: a second client name reuses the CA and the localhost server certificate and leaves the first client alone" {
    cd "$WORKDIR"
    local d="$TT/o" before
    make_full_set "$d"
    before=$(snapshot "$d")
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Using existing server certificate localhost.crt"* ]]
    [ -s "$d/bob.key" ]
    [ -s "$d/bob.crt" ]
    [ -s "$d/bob.p12" ]
    run openssl verify -CAfile "$d/ca.crt" "$d/bob.crt"
    [ "$status" -eq 0 ]
    # Every file that was there is byte-identical, except the serial counter.
    [ "$(snapshot "$d" | /usr/bin/grep -v -e ' ca.srl$' -e ' bob\.' | sort)" = "$(printf '%s\n' "$before" | /usr/bin/grep -v ' ca.srl$' | sort)" ]
}

@test "existing files: a second client reuses a server certificate made for other domains, and --force makes a new one" {
    cd "$WORKDIR"
    local d="$TT/o" old
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --domain a.example --domain 10.0.0.1
    [ "$status" -eq 0 ]
    old=$(sha256sum < "$d/server.key")
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" --domain a.example --domain 10.0.0.1
    [ "$status" -eq 0 ]
    [[ "$output" == *"Using existing server certificate server.crt"* ]]
    [ "$(sha256sum < "$d/server.key")" = "$old" ]
    run timeout 60 "$GEN_SCRIPT" carol -k 2048 -o "$d" --domain b.example --force
    [ "$status" -eq 0 ]
    [ "$(sha256sum < "$d/server.key")" != "$old" ]
    run openssl x509 -in "$d/server.crt" -noout -ext subjectAltName
    [[ "$output" == *"DNS:b.example"* ]]
}

@test "existing files: a server key without its certificate, or the reverse, is refused" {
    cd "$WORKDIR"
    local d="$TT/o" gone
    for gone in crt key; do
        rm -rf -- "${d:?}"
        make_full_set "$d"
        rm -- "${d:?}/localhost.${gone:?}"
        assert_refusal_changes_nothing "$d" "only one of localhost.crt and localhost.key" bob
    done
}

@test "existing files: a ca-trusted.crt that is not the CA certificate is refused, and --force replaces it" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d"
    printf 'not a certificate\n' > "$d/ca-trusted.crt"
    assert_refusal_changes_nothing "$d" "$d/ca-trusted.crt already exists" bob
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" --force
    [ "$status" -eq 0 ]
    cmp "$d/ca.crt" "$d/ca-trusted.crt"
}

@test "existing files: --force replaces the client files with new ones signed by the same CA, and leaves the CA alone" {
    cd "$WORKDIR"
    local d="$TT/o" ca_before key_before left
    make_full_set "$d"
    ca_before=$(sha256sum < "$d/ca.key")$(sha256sum < "$d/ca.crt")
    key_before=$(sha256sum < "$d/alice.key")
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
    [ "$status" -eq 0 ]
    [ "$(sha256sum < "$d/alice.key")" != "$key_before" ]
    [ "$(sha256sum < "$d/ca.key")$(sha256sum < "$d/ca.crt")" = "$ca_before" ]
    run openssl verify -CAfile "$d/ca.crt" "$d/alice.crt"
    [ "$status" -eq 0 ]
    [ "$(openssl x509 -in "$d/alice.crt" -noout -pubkey)" = "$(openssl pkey -in "$d/alice.key" -pubout)" ]
    shopt -s nullglob dotglob
    left=("$d"/.staging.*)
    shopt -u nullglob dotglob
    [ "${#left[@]}" -eq 0 ]
}

@test "existing files: a forced run that fails at the client certificate keeps the old key, certificate and bundle byte for byte" {
    cd "$WORKDIR"
    local d="$TT/o" before real
    make_full_set "$d"
    before=$(snapshot "$d")
    real=$(command -v openssl)
    mkdir -p "$TT/failleaf"
    printf '#!/bin/sh\ncase "$*" in *"x509 -req"*alice.crt*) exit 1 ;; esac\nexec %s "$@"\n' "$real" > "$TT/failleaf/openssl"
    chmod +x "$TT/failleaf/openssl"
    PATH="$TT/failleaf:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
    [ "$status" -ne 0 ]
    [[ "$output" == *"step failed: sign client certificate"* ]]
    [ "$(snapshot "$d")" = "$before" ]
}

@test "existing files: a run that fails at the server certificate adds nothing and leaves the serial counter alone" {
    cd "$WORKDIR"
    local d="$TT/o" before real
    make_full_set "$d"
    before=$(snapshot "$d")
    real=$(command -v openssl)
    mkdir -p "$TT/failsrv"
    printf '#!/bin/sh\ncase "$*" in *"x509 -req"*server.crt*) exit 1 ;; esac\nexec %s "$@"\n' "$real" > "$TT/failsrv/openssl"
    chmod +x "$TT/failsrv/openssl"
    PATH="$TT/failsrv:$PATH" run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" --domain new.example
    [ "$status" -ne 0 ]
    [[ "$output" == *"step failed: sign server certificate"* ]]
    [ "$(snapshot "$d")" = "$before" ]
}

@test "half-made CA: only ca.key, or only ca.crt, is refused with a message to restore the file or empty the folder, even with --force" {
    cd "$WORKDIR"
    local d="$TT/o" gone
    for gone in key crt; do
        rm -rf -- "${d:?}"
        make_full_set "$d"
        rm -- "${d:?}/ca.${gone:?}"
        assert_refusal_changes_nothing "$d" "only one of ca.key and ca.crt" bob
        [[ "$output" == *"restore the missing file or empty the folder"* ]]
        assert_refusal_changes_nothing "$d" "only one of ca.key and ca.crt" bob --force
    done
}

@test "half-made CA: no CA but a leaf certificate is refused, even with --force, and no new CA is made" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d"
    rm -- "${d:?}/ca.key" "${d:?}/ca.crt"
    assert_refusal_changes_nothing "$d" "but no CA" bob
    [[ "$output" == *"restore the CA or empty the folder"* ]]
    assert_refusal_changes_nothing "$d" "but no CA" bob --force
    [ ! -e "$d/ca.key" ]
}

@test "symlinks: a link planted at any file in the folder is refused, its target is unchanged, and the run writes nothing" {
    cd "$WORKDIR"
    local d="$TT/o" name target_sum
    make_full_set "$d" bob
    printf 'precious\n' > "$TT/target"
    target_sum=$(sha256sum < "$TT/target")
    for name in alice.key alice.crt alice.p12 ca.srl unrelated; do
        ln -sf "$TT/target" "$d/$name"
        assert_refusal_changes_nothing "$d" "$d/$name is a symbolic link" alice
        assert_refusal_changes_nothing "$d" "$d/$name is a symbolic link" alice --force
        [ "$(sha256sum < "$TT/target")" = "$target_sum" ]
        rm -- "${d:?}/${name:?}"
    done
    ln -s "$TT/nowhere" "$d/alice.key"
    assert_refusal_changes_nothing "$d" "$d/alice.key is a symbolic link" alice
    [ ! -e "$TT/nowhere" ]
}

@test "symlinks: a link in place of ca.key is refused and is not used to sign" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d" bob
    mv "$d/ca.key" "$TT/real-ca.key"
    ln -s "$TT/real-ca.key" "$d/ca.key"
    assert_refusal_changes_nothing "$d" "$d/ca.key is a symbolic link" alice
}

@test "folder contents: a directory or a named pipe is refused, naming it" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d" bob
    mkdir "$d/sub"
    assert_refusal_changes_nothing "$d" "$d/sub is not a regular file" alice
    rmdir "$d/sub"
    mkfifo "$d/pipe"
    assert_refusal_changes_nothing "$d" "$d/pipe is not a regular file" alice
    rm -- "${d:?}/pipe"
}

@test "folder contents: a file owned by another user is refused, naming it" {
    [ "$(id -u)" -eq 0 ] || skip "needs root to make a file owned by another user"
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d" bob
    printf 'x\n' > "$d/foreign.txt"
    chown 1:1 "$d/foreign.txt"
    assert_refusal_changes_nothing "$d" "$d/foreign.txt is not owned by you" alice
}

@test "marker: a folder the script made has .uudex-certs and works again for a new client; a failed first run leaves an empty folder that works" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d"
    [ -f "$d/.uudex-certs" ]
    [ ! -L "$d/.uudex-certs" ]
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -eq 0 ]
    fake_openssl_failing
    PATH="$FAKEBIN:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/first"
    [ "$status" -ne 0 ]
    [ -z "$(ls -A "$TT/first")" ]
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/first"
    [ "$status" -eq 0 ]
}

@test "marker: a hand-made folder with files is refused and untouched, and an empty hand-made folder is accepted and marked" {
    cd "$WORKDIR"
    local d="$TT/hand"
    mkdir -m 700 "$d"
    printf 'mine\n' > "$d/notes.txt"
    assert_refusal_changes_nothing "$d" "has no .uudex-certs marker" alice
    [ "$(cat "$d/notes.txt")" = "mine" ]
    rm -- "${d:?}/notes.txt"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d"
    [ "$status" -eq 0 ]
    [ -f "$d/.uudex-certs" ]
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -eq 0 ]
}

@test "marker: a planted ca.key in a hand-made folder is refused, not used to sign" {
    cd "$WORKDIR"
    local d="$TT/hand"
    mkdir -m 700 "$d"
    openssl genrsa -out "$d/ca.key" 2048
    assert_refusal_changes_nothing "$d" "has no .uudex-certs marker" alice
}

@test "parents: a parent that others or the group can write is refused, naming it, and nothing is made below it" {
    cd "$WORKDIR"
    local m
    for m in 777 775 757 1777; do
        mkdir -p "$TT/p$m"
        chmod "$m" "$TT/p$m"
        run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/p$m/new/out"
        [ "$status" -ne 0 ] || { echo "accepted parent mode $m"; return 1; }
        [[ "$output" == *"$TT/p$m, a parent of output folder"*"writable by other users"* ]] || { echo "$m: $output"; return 1; }
        [ -z "$(ls -A "$TT/p$m")" ]
        mkdir -m 700 "$TT/p$m/out"
        run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/p$m/out"
        [ "$status" -ne 0 ]
        [ -z "$(ls -A "$TT/p$m/out")" ]
    done
}

@test "parents: a writable grandparent is refused, not only the direct parent" {
    cd "$WORKDIR"
    mkdir -p "$TT/g/p"
    chmod 775 "$TT/g"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/g/p/out"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$TT/g, a parent of output folder"* ]]
    [ ! -e "$TT/g/p/out" ]
}

# Teardown removes this folder, so a run with a broken parent check does not
# leave keys in /tmp. BATS_CERTS_TMP is for proof runs only: it must name a path
# that does not exist yet, and a path outside /tmp makes this test fail.
@test "parents: a folder under /tmp is refused, naming /tmp, and nothing is made" {
    local mode d="${BATS_CERTS_TMP:-/tmp/uudex-certs-bats-$$-x}"
    [ ! -e "$d" ] || { echo "$d already exists; BATS_CERTS_TMP must name a new path"; return 1; }
    TMP_CASE_DIR="$d"
    mode=$(ls -ld /tmp)
    [ "${mode:8:1}" = "w" ] || skip "/tmp is not writable by others here"
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [[ "$output" == *"/tmp, a parent of output folder"* ]]
    [ ! -e "$d" ]
}

@test "parents: a parent owned by neither you nor root is refused; the same run passes when the owner is you" {
    [ "$(id -u)" -ne 0 ] || skip "root owns every parent it can reach"
    cd "$WORKDIR"
    local real_id
    real_id=$(command -v id)
    mkdir -p "$TT/fakeid"
    printf '#!/bin/sh\ncase "$*" in -u) echo 4242 ;; *) exec %s "$@" ;; esac\n' "$real_id" > "$TT/fakeid/id"
    chmod +x "$TT/fakeid/id"
    PATH="$TT/fakeid:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"is owned by neither you nor root"* ]]
    [ ! -e "$TT/o" ]
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/o"
    [ "$status" -eq 0 ]
}

@test "parents: a normal layout under the home folder works, and a second client works on the default folder" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048
    [ "$status" -eq 0 ]
    run timeout 60 "$GEN_SCRIPT" bob -k 2048
    [ "$status" -eq 0 ]
    [ -s "$FAKE_HOME/.config/uudex/tls/bob.key" ]
    run timeout 60 "$GEN_SCRIPT" alice -k 2048
    [ "$status" -ne 0 ]
    [[ "$output" == *"$FAKE_HOME/.config/uudex/tls/alice.key already exists"* ]]
}

@test "output folder links: a symlinked output folder is refused; a link in a parent is followed and the real parents are checked" {
    cd "$WORKDIR"
    mkdir -m 700 "$TT/real"
    ln -s "$TT/real" "$TT/link"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/link"
    [ "$status" -ne 0 ]
    [[ "$output" == *"is a symbolic link"* ]]
    [ -z "$(ls -A "$TT/real")" ]
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/link/out"
    [ "$status" -eq 0 ]
    [ -s "$TT/real/out/alice.key" ]
    mkdir -m 777 "$TT/open"
    chmod 777 "$TT/open"
    ln -s "$TT/open" "$TT/openlink"
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$TT/openlink/out"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$TT/open, a parent of output folder"* ]]
    [ -z "$(ls -A "$TT/open")" ]
}

# The move into the folder is all or nothing.

# A mv that fails, or plants something first, when its arguments match a
# pattern; it runs the real mv otherwise. $1 is the pattern, $2 an optional
# command to run before the real mv.
stub_mv() {
    local real
    real=$(command -v mv)
    MVBIN="$TT/mvbin"
    mkdir -p "$MVBIN"
    cat > "$MVBIN/mv" <<STUBEOF
#!/bin/bash
if [[ "\$*" =~ $1 ]]; then
    ${2:-exit 1}
fi
exec $real "\$@"
STUBEOF
    chmod +x "$MVBIN/mv"
}

same_pair() {
    [ "$(openssl x509 -in "$1.crt" -noout -pubkey)" = "$(openssl pkey -in "$1.key" -pubout)" ]
}

@test "all or nothing: a forced move that fails part-way puts every file back, keeps the key and certificate pair, and names the files" {
    cd "$WORKDIR"
    local d="$TT/o" before
    make_full_set "$d"
    before=$(snapshot "$d")
    stub_mv '\.staging\.[[:alnum:]]{6}/localhost\.key'
    PATH="$MVBIN:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
    [ "$status" -ne 0 ]
    [[ "$output" == *"put back as they were"*"localhost.crt"* ]] || { echo "$output"; return 1; }
    [ "$(snapshot "$d")" = "$before" ]
    same_pair "$d/localhost"
    same_pair "$d/alice"
}

@test "all or nothing: a first run whose move fails between the CA certificate and the CA key leaves an empty folder" {
    cd "$WORKDIR"
    local d="$TT/first"
    stub_mv '\.staging\.[[:alnum:]]{6}/ca\.key'
    PATH="$MVBIN:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [ -z "$(ls -A "$d")" ] || { ls -A "$d"; return 1; }
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d"
    [ "$status" -eq 0 ]
}

@test "all or nothing: a folder planted at a destination during the run gets nothing moved into it, and the run fails" {
    cd "$WORKDIR"
    local d="$TT/o" real
    make_full_set "$d"
    real=$(command -v openssl)
    mkdir -p "$TT/plant"
    printf '#!/bin/sh\ncase "$*" in *"pkcs12 -export"*) mkdir -p "%s/bob.key" ;; esac\nexec %s "$@"\n' "$d" "$real" > "$TT/plant/openssl"
    chmod +x "$TT/plant/openssl"
    PATH="$TT/plant:$PATH" run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$d/bob.key is a link or a folder that appeared while this run was working"* ]] || { echo "$output"; return 1; }
    [ -z "$(ls -A "$d/bob.key")" ]
    [ ! -e "$d/bob.crt" ]
}

@test "all or nothing: a link to a folder planted at a destination of a forced run is not followed" {
    cd "$WORKDIR"
    local d="$TT/o" real
    make_full_set "$d"
    mkdir -p "$TT/elsewhere"
    real=$(command -v openssl)
    mkdir -p "$TT/plant"
    printf '#!/bin/sh\ncase "$*" in *"pkcs12 -export"*) rm -f "%s/alice.key"; ln -s "%s/elsewhere" "%s/alice.key" ;; esac\nexec %s "$@"\n' "$d" "$TT" "$d" "$real" > "$TT/plant/openssl"
    chmod +x "$TT/plant/openssl"
    PATH="$TT/plant:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
    [ "$status" -ne 0 ]
    [ -z "$(ls -A "$TT/elsewhere")" ]
}

@test "all or nothing: a folder that appears at a destination between the check and the move gets no key" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d"
    stub_mv '\.staging\.[[:alnum:]]{6}/bob\.key ' "mkdir -p '$d/bob.key'"
    PATH="$MVBIN:$PATH" run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$d/bob.key is not a regular file after the move"* ]] || { echo "$output"; return 1; }
    [ -z "$(ls -A "$d/bob.key")" ]
}

@test "all or nothing: a file planted during the run is kept as it is, the run fails, and nothing else of the run stays" {
    cd "$WORKDIR"
    local d="$TT/o" real before expected
    make_full_set "$d"
    before=$(snapshot "$d")
    real=$(command -v openssl)
    mkdir -p "$TT/plant"
    printf '#!/bin/sh\ncase "$*" in *"pkcs12 -export"*) printf planted > "%s/bob.p12" ;; esac\nexec %s "$@"\n' "$d" "$real" > "$TT/plant/openssl"
    chmod +x "$TT/plant/openssl"
    PATH="$TT/plant:$PATH" run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$d/bob.p12 appeared while this run was working"* ]] || { echo "$output"; return 1; }
    [ "$(cat "$d/bob.p12")" = "planted" ]
    expected=$(printf '%s\n%s bob.p12\n' "$before" "$(printf planted | sha256sum | cut -c1-64)" | sort)
    [ "$(snapshot "$d" | sort)" = "$expected" ]
}

# A mv that runs the real one and then sends signal $1 to the script when its
# arguments match $2. Bash runs the trap when the mv returns, so the file is
# already in place when the rollback starts.
stub_mv_signal() {
    local real
    real=$(command -v mv)
    MVBIN="$TT/mvbin"
    mkdir -p "$MVBIN"
    cat > "$MVBIN/mv" <<STUBEOF
#!/bin/bash
if [[ "\$*" =~ $2 ]]; then
    $real "\$@"
    kill -s $1 \$PPID
    exit 0
fi
exec $real "\$@"
STUBEOF
    chmod +x "$MVBIN/mv"
}

modes_of() { stat -c '%a %n' "$1"/*; }

# $1 signal, $2 the exit status the script gives for it. The signal lands while
# a replaced file (forced run) and then a new file (plain run) is being moved.
# The output and status are read into locals, not through run, so shellcheck
# does not flag this helper as a subshell reader of $status.
assert_signal_during_move_rolled_back() {
    cd "$WORKDIR" || return 1
    local d="$TT/o" before modes out rc=0
    make_full_set "$d"
    before=$(snapshot "$d")
    modes=$(modes_of "$d")
    stub_mv_signal "$1" '\.staging\.[[:alnum:]]{6}/localhost\.key '
    out=$(PATH="$MVBIN:$PATH" timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force 2>&1) || rc=$?
    [ "$rc" -eq "$2" ] || { echo "status $rc: $out"; return 1; }
    [[ "$out" == *"put back as they were: localhost.key localhost.crt"* ]] || { echo "$out"; return 1; }
    [ "$(snapshot "$d")" = "$before" ]
    [ "$(modes_of "$d")" = "$modes" ]
    same_pair "$d/localhost"
    same_pair "$d/alice"
    stub_mv_signal "$1" '\.staging\.[[:alnum:]]{6}/bob\.key '
    rc=0
    out=$(PATH="$MVBIN:$PATH" timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" 2>&1) || rc=$?
    [ "$rc" -eq "$2" ] || { echo "status $rc: $out"; return 1; }
    [[ "$out" == *"removed because this run made them: bob.key bob.crt"* ]] || { echo "$out"; return 1; }
    [ "$(snapshot "$d")" = "$before" ]
    [ "$(modes_of "$d")" = "$modes" ]
    timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" > /dev/null 2>&1
    same_pair "$d/bob"
}

@test "all or nothing: INT during a move puts every file back, the file in flight included" {
    assert_signal_during_move_rolled_back INT 130
}

@test "all or nothing: TERM during a move puts every file back, the file in flight included" {
    assert_signal_during_move_rolled_back TERM 143
}

@test "all or nothing: HUP during a move puts every file back, the file in flight included" {
    assert_signal_during_move_rolled_back HUP 129
}

# A mv that runs the real one and sends signal $1 to the script when it moves
# a staged localhost.key into place, and signal $2 after the first restore from
# the .old folder. Used to send a second signal while the rollback is running.
stub_mv_two_signals() {
    local real
    real=$(command -v mv)
    MVBIN="$TT/mvbin"
    mkdir -p "$MVBIN"
    cat > "$MVBIN/mv" <<STUBEOF
#!/bin/bash
if [[ "\$*" =~ \.staging\.[[:alnum:]]{6}/localhost\.key ]]; then
    $real "\$@"
    kill -s $1 \$PPID
    exit 0
fi
if [[ "\$*" =~ \.staging\.[[:alnum:]]{6}/\.old/ ]]; then
    $real "\$@"
    kill -s $2 \$PPID
    exit 0
fi
exec $real "\$@"
STUBEOF
    chmod +x "$MVBIN/mv"
}

# $1 first signal, $2 second signal, $3 the exit status for the first one.
assert_second_signal_during_rollback_ignored() {
    cd "$WORKDIR" || return 1
    local d="$TT/o" before modes out rc=0
    make_full_set "$d"
    before=$(snapshot "$d")
    modes=$(modes_of "$d")
    stub_mv_two_signals "$1" "$2"
    out=$(PATH="$MVBIN:$PATH" timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force 2>&1) || rc=$?
    [ "$rc" -eq "$3" ] || { echo "status $rc: $out"; return 1; }
    [[ "$out" == *"put back as they were: localhost.key localhost.crt"* ]] || { echo "$out"; return 1; }
    [ "$(snapshot "$d")" = "$before" ]
    [ "$(modes_of "$d")" = "$modes" ]
    same_pair "$d/localhost"
    same_pair "$d/alice"
    [ -z "$(ls -A "$d" | /usr/bin/grep '^\.staging\.' || true)" ]
}

@test "all or nothing: a second TERM during the rollback is ignored and every old file is still put back" {
    assert_second_signal_during_rollback_ignored INT TERM 130
}

@test "all or nothing: a second INT during the rollback is ignored and every old file is still put back" {
    assert_second_signal_during_rollback_ignored INT INT 130
}

# A mv that swaps the destination for a folder (after removing a file there)
# just before the real move of a staged file matching $1. The file then lands
# inside the folder, and the script finds no regular file at the destination.
@test "a folder swapped in at the destination of a forced move: the old file stays in the kept staging folder, which the message names" {
    cd "$WORKDIR"
    local d="$TT/o" before stage out rc=0
    make_full_set "$d"
    before=$(snapshot "$d")
    stub_mv '\.staging\.[[:alnum:]]{6}/localhost\.key ' "rm -f '$d/localhost.key'; mkdir '$d/localhost.key'"
    out=$(PATH="$MVBIN:$PATH" timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force 2>&1) || rc=$?
    [ "$rc" -ne 0 ]
    [[ "$out" == *"is not a regular file after the move"* ]] || { echo "$out"; return 1; }
    stage=$(echo "$d"/.staging.*)
    [ -d "$stage/.old" ] || { echo "$out"; return 1; }
    [[ "$out" == *"left alone because a link or a folder is in their place: localhost.key"* ]] || { echo "$out"; return 1; }
    [[ "$out" == *"the old files are kept in $stage/.old: "*"localhost.key"* ]] || { echo "$out"; return 1; }
    [[ $'\n'"$before"$'\n' == *$'\n'"$(sha256sum < "$stage/.old/localhost.key" | cut -c1-64) localhost.key"$'\n'* ]] || { echo "the old key is not in .old"; return 1; }
}

@test "a folder swapped in at the destination of a plain move: the message is true, the new files are removed, and no staging folder is left" {
    cd "$WORKDIR"
    local d="$TT/o" out rc=0
    make_full_set "$d"
    stub_mv '\.staging\.[[:alnum:]]{6}/bob\.key ' "mkdir '$d/bob.key'"
    out=$(PATH="$MVBIN:$PATH" timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" 2>&1) || rc=$?
    [ "$rc" -ne 0 ]
    [[ "$out" == *"is not a regular file after the move"* ]] || { echo "$out"; return 1; }
    [[ "$out" == *"removed because this run made them: bob.crt"* ]] || { echo "$out"; return 1; }
    [[ "$out" != *"could not be fully undone"* ]] || { echo "$out"; return 1; }
    [ -z "$(ls -A "$d" | /usr/bin/grep '^\.staging\.' || true)" ]
}

@test "all or nothing: when a file cannot be put back the staging folder and the old files are kept and named, and the run fails" {
    cd "$WORKDIR"
    local d="$TT/o" before stage name
    make_full_set "$d"
    before=$(snapshot "$d")
    stub_mv '\.staging\.[[:alnum:]]{6}/localhost\.key|\.old/'
    PATH="$MVBIN:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
    [ "$status" -ne 0 ]
    stage=$(echo "$d"/.staging.*)
    [ -d "$stage/.old" ] || { echo "$output"; return 1; }
    [[ "$output" == *"could not put back or remove: localhost.crt"* ]] || { echo "$output"; return 1; }
    [[ "$output" == *"the old files are kept in $stage/.old: "*"localhost.crt"* ]] || { echo "$output"; return 1; }
    for name in alice.crt alice.key alice.p12 ca.srl localhost.crt localhost.key; do
        [[ $'\n'"$before"$'\n' == *$'\n'"$(sha256sum < "$stage/.old/$name" | cut -c1-64) $name"$'\n'* ]] || { echo "$name in .old is not the old file"; return 1; }
    done
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [[ "$output" == *"first move the files in $stage/.old back into $d"* ]] || { echo "$output"; return 1; }
    rm -f -- "${d:?}/localhost.crt" "${d:?}/localhost.key" "${d:?}/alice.crt" "${d:?}/alice.key" "${d:?}/alice.p12" "${d:?}/ca.srl"
    mv -- "$stage"/.old/* "$d"/
    rm -r -- "${stage:?}"
    [ "$(snapshot "$d")" = "$before" ]
    same_pair "$d/localhost"
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -eq 0 ]
}

@test "all or nothing: a link or a folder planted where an old file goes back is not followed, the old file stays in the staging folder, and the message says so" {
    cd "$WORKDIR"
    local d="$TT/o" kind stage plant
    for kind in link folder; do
        rm -rf -- "${d:?}" "${TT:?}/elsewhere"
        mkdir -p "$TT/elsewhere"
        make_full_set "$d"
        if [ "$kind" = link ]; then
            plant="ln -s '$TT/elsewhere' '$d/localhost.crt'"
        else
            plant="mkdir '$d/localhost.crt'"
        fi
        stub_mv '\.staging\.[[:alnum:]]{6}/localhost\.key' "rm -f '$d/localhost.crt'; $plant; exit 1"
        PATH="$MVBIN:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
        [ "$status" -ne 0 ]
        stage=$(echo "$d"/.staging.*)
        [[ "$output" == *"left alone because a link or a folder is in their place: localhost.crt"* ]] || { echo "$kind: $output"; return 1; }
        [ -f "$stage/.old/localhost.crt" ]
        [ -z "$(ls -A "$TT/elsewhere")" ] || { echo "$kind: followed"; return 1; }
        [ -z "$(ls -A "$d/localhost.crt")" ]
    done
}

@test "all or nothing: where hard links are refused, a copy keeps the old files, a forced run works, and a failed move still restores them with their modes" {
    cd "$WORKDIR"
    local d="$TT/o" before modes
    make_full_set "$d"
    mkdir -p "$TT/nolink"
    printf '#!/bin/sh\nexit 1\n' > "$TT/nolink/ln"
    chmod +x "$TT/nolink/ln"
    PATH="$TT/nolink:$PATH" run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -eq 0 ] || { echo "$output"; return 1; }
    before=$(snapshot "$d")
    modes=$(modes_of "$d")
    stub_mv '\.staging\.[[:alnum:]]{6}/localhost\.key'
    PATH="$MVBIN:$TT/nolink:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
    [ "$status" -ne 0 ]
    [[ "$output" == *"put back as they were"* ]] || { echo "$output"; return 1; }
    [ "$(snapshot "$d")" = "$before" ]
    [ "$(modes_of "$d")" = "$modes" ]
    PATH="$TT/nolink:$PATH" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --force
    [ "$status" -eq 0 ] || { echo "$output"; return 1; }
    same_pair "$d/alice"
}

@test "all or nothing: a file that appears between the check and the move is kept, the run fails, and nothing else of the run stays" {
    cd "$WORKDIR"
    local d="$TT/o" before expected
    make_full_set "$d"
    before=$(snapshot "$d")
    stub_mv '\.staging\.[[:alnum:]]{6}/bob\.p12 ' "printf planted > '$d/bob.p12'"
    PATH="$MVBIN:$PATH" run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$d/bob.p12 appeared while this run was working"* ]] || { echo "$output"; return 1; }
    [[ "$output" != *"successfully"* ]]
    [ "$(cat "$d/bob.p12")" = "planted" ]
    expected=$(printf '%s\n%s bob.p12\n' "$before" "$(printf planted | sha256sum | cut -c1-64)" | sort)
    [ "$(snapshot "$d" | sort)" = "$expected" ]
}

# A reused server pair, key modes and server names are checked.

@test "reused server pair: a key that does not match the certificate is refused, naming both files, and nothing changes" {
    cd "$WORKDIR"
    local d="$TT/o" before
    make_full_set "$d"
    openssl genrsa -out "$d/localhost.key" 2048
    chmod 600 "$d/localhost.key"
    before=$(snapshot "$d")
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$d/localhost.crt and $d/localhost.key do not belong together"* ]] || { echo "$output"; return 1; }
    [[ "$output" != *"successfully"* ]]
    [ "$(snapshot "$d")" = "$before" ]
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" --force
    [ "$status" -eq 0 ]
    same_pair "$d/localhost"
}

@test "reused keys: a CA key or a server key that others can read is refused, naming it, until it is private again" {
    cd "$WORKDIR"
    local d="$TT/o" k
    make_full_set "$d"
    for k in ca localhost; do
        chmod 640 "$d/$k.key"
        assert_refusal_changes_nothing "$d" "$d/$k.key can be read or changed by other users" bob
        chmod 604 "$d/$k.key"
        assert_refusal_changes_nothing "$d" "$d/$k.key can be read or changed by other users" bob
        chmod 620 "$d/$k.key"
        assert_refusal_changes_nothing "$d" "$d/$k.key can be read or changed by other users" bob
        chmod 602 "$d/$k.key"
        assert_refusal_changes_nothing "$d" "$d/$k.key can be read or changed by other users" bob
        chmod 600 "$d/$k.key"
    done
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -eq 0 ]
}

@test "--server-only over a server certificate for other names is refused, pointing to --force, and the certificate is unchanged" {
    cd "$WORKDIR"
    local d="$TT/o" before
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain a.example --domain b.example
    [ "$status" -eq 0 ]
    before=$(snapshot "$d")
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain c.example
    [ "$status" -ne 0 ]
    [[ "$output" == *"already exists for the names a.example b.example, not the requested c.example"*"--force"* ]] || { echo "$output"; return 1; }
    [[ "$output" != *"completed"* ]]
    [ "$(snapshot "$d")" = "$before" ]
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain c.example --force
    [ "$status" -eq 0 ]
    run openssl x509 -in "$d/server.crt" -noout -ext subjectAltName
    [[ "$output" == *"DNS:c.example"* && "$output" != *"a.example"* ]]
}

@test "--server-only over a certificate with more names, or another address, is refused and the certificate is unchanged" {
    cd "$WORKDIR"
    local d="$TT/o" before
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain a.example --domain b.example
    [ "$status" -eq 0 ]
    before=$(snapshot "$d")
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain a.example
    [ "$status" -ne 0 ]
    [[ "$output" == *"already exists for the names a.example b.example, not the requested a.example,"* ]] || { echo "$output"; return 1; }
    [ "$(snapshot "$d")" = "$before" ]
    rm -rf -- "${d:?}"
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain a.example --domain 10.0.0.1
    [ "$status" -eq 0 ]
    before=$(snapshot "$d")
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain a.example --domain 10.0.0.2
    [ "$status" -ne 0 ]
    [[ "$output" == *"already exists for the names a.example 10.0.0.1, not the requested a.example 10.0.0.2"* ]] || { echo "$output"; return 1; }
    [ "$(snapshot "$d")" = "$before" ]
}

@test "--server-only over a server certificate for the same names succeeds, including an address written another way" {
    cd "$WORKDIR"
    local d="$TT/o"
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain a.example --domain 10.0.0.1 --domain fe80::1
    [ "$status" -eq 0 ]
    run timeout 60 "$GEN_SCRIPT" --server-only Org -k 2048 -o "$d" --domain 10.0.0.1 --domain a.example --domain fe80:0:0::1
    [ "$status" -eq 0 ] || { echo "$output"; return 1; }
    [[ "$output" == *"Domains: a.example 10.0.0.1 FE80:0:0:0:0:0:0:1"* ]]
}

@test "a client run over a server certificate for other names warns on stderr and the summary shows the names in the certificate" {
    cd "$WORKDIR"
    local d="$TT/o"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$d" --domain a.example
    [ "$status" -eq 0 ]
    run --separate-stderr timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d" --domain z.example
    [ "$status" -eq 0 ]
    [[ "$stderr" == *"is for the names a.example, not the requested z.example"* ]] || { echo "$stderr"; return 1; }
    [[ "$output" == *"Server Domains: a.example"* ]]
    [[ "$output" != *"z.example"* ]]
}

@test "--server-only writes keys 0600 and certificates 0644 whatever the umask" {
    cd "$WORKDIR"
    local d="$TT/o" f mode
    run bash -c 'umask 002; exec timeout 60 "$0" --server-only Org -k 2048 -o "$1" --domain a.example' "$GEN_SCRIPT" "$d"
    [ "$status" -eq 0 ]
    for f in ca.key server.key; do
        mode=$(ls -l "$d/$f")
        [ "${mode:0:10}" = "-rw-------" ] || { echo "$f $mode"; return 1; }
    done
    for f in ca.crt ca-trusted.crt server.crt; do
        mode=$(ls -l "$d/$f")
        [ "${mode:0:10}" = "-rw-r--r--" ] || { echo "$f $mode"; return 1; }
    done
}

@test "a folder without the marker is refused with a message that it may come from an older version and how to adopt it; the marker makes it work" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d"
    rm -- "${d:?}/.uudex-certs"
    assert_refusal_changes_nothing "$d" "has no .uudex-certs marker" bob
    [[ "$output" == *"older version"*"create an empty file named .uudex-certs"* ]] || { echo "$output"; return 1; }
    : > "$d/.uudex-certs"
    run timeout 60 "$GEN_SCRIPT" bob -k 2048 -o "$d"
    [ "$status" -eq 0 ]
    run openssl verify -CAfile "$d/ca.crt" "$d/bob.crt"
    [ "$status" -eq 0 ]
}

@test "a staging folder left by a cut-off run is named as such, left in place, and the run is refused" {
    cd "$WORKDIR"
    local d="$TT/o"
    make_full_set "$d"
    mkdir -m 700 "$d/.staging.abc123"
    assert_refusal_changes_nothing "$d" "$d/.staging.abc123 is a staging folder left by a run of this script" bob
    [[ "$output" == *"first move the files in $d/.staging.abc123/.old back into $d"*"then remove the staging folder with rm -r"* ]] || { echo "$output"; return 1; }
    [ -d "$d/.staging.abc123" ]
}

@test "output folder: a '..' below a folder that does not exist yet is refused, and the folder it would reach stays empty" {
    cd "$WORKDIR"
    mkdir -m 777 "$TT/open"
    chmod 777 "$TT/open"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$TT/nx/../open/out"
    [ "$status" -ne 0 ]
    [[ "$output" == *"has a '.' or '..' part below a folder that does not exist yet"* ]] || { echo "$output"; return 1; }
    [ -z "$(ls -A "$TT/open")" ]
    [ ! -e "$TT/nx" ]
}

@test "client names: ca, ca-trusted, server and localhost are refused before the folder is made; a similar name is fine" {
    cd "$WORKDIR"
    local n
    spy_openssl
    for n in ca ca-trusted server localhost; do
        PATH="$SPYBIN:$PATH" run timeout 60 "$GEN_SCRIPT" "$n" -k 2048 -o "$TT/n-$n"
        [ "$status" -ne 0 ] || { echo "accepted $n"; return 1; }
        [[ "$output" == *"client name '$n' would overwrite the CA or server files"* ]]
        [ ! -e "$TT/n-$n" ]
    done
    [ ! -s "$SPYLOG" ]
    run timeout 60 "$GEN_SCRIPT" ca2 -k 2048 -o "$TT/n-ca2"
    [ "$status" -eq 0 ]
}

@test "help describes --force" {
    run "$GEN_SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"--force"*"never the CA"* ]]
}
