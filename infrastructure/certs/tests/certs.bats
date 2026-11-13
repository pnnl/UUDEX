#!/usr/bin/env bats

SCRIPTS="$BATS_TEST_DIRNAME/.."
REPO_GITIGNORE="$BATS_TEST_DIRNAME/../../../.gitignore"
PG_SCRIPT="$SCRIPTS/generate-certs-from-existing-postgres.sh"
GEN_SCRIPT="$SCRIPTS/generate-certs.sh"
ALL_FILES="alice.crt alice.key alice.p12 ca.crt ca.key ca-trusted.crt"

setup() {
    FAKE_HOME="$BATS_TEST_TMPDIR/home"
    WORKDIR="$BATS_TEST_TMPDIR/work"
    mkdir -p "$FAKE_HOME" "$WORKDIR"
    export HOME="$FAKE_HOME"
    unset UUDEX_CERTS UUDEX_CERTS_CONF DB_PASSWORD

    # psql stub: records each call and answers the three queries the script makes.
    STUB="$BATS_TEST_TMPDIR/stub"
    PSQL_LOG="$BATS_TEST_TMPDIR/psql.log"
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

# A throwaway repository holding a copy of the real .gitignore, isolated from
# the developer's global git config, so the checks can fail on untracked paths.
ignore_repo() {
    [ -f "$REPO_GITIGNORE" ] || skip "no .gitignore next to the source tree"
    IGN="$BATS_TEST_TMPDIR/ignrepo"
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
    UUDEX_CERTS="$BATS_TEST_TMPDIR/custom" run "$GEN_SCRIPT" alice -k 2048
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/custom/alice.key" ]
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
}

@test "generate-certs.sh -o writes to the given folder" {
    cd "$WORKDIR"
    run "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/dash-o"
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/dash-o/alice.key" ]
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
    run env -u HOME -u UUDEX_CERTS "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/nohome"
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/nohome/alice.key" ]
}

@test "generate-certs.sh creates the output folder with mode 700" {
    cd "$WORKDIR"
    run "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/private"
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$BATS_TEST_TMPDIR/private")" = "700" ]
}

@test "generate-certs.sh refuses an output folder that group or others can write" {
    cd "$WORKDIR"
    for m in 775 757 777; do
        mkdir -p "$BATS_TEST_TMPDIR/shared$m"
        chmod "$m" "$BATS_TEST_TMPDIR/shared$m"
        run "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/shared$m"
        [ "$status" -ne 0 ] || { echo "accepted mode $m"; return 1; }
        [[ "$output" == *"writable"* ]]
        [ -z "$(ls -A "$BATS_TEST_TMPDIR/shared$m")" ]
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
    UUDEX_CERTS="$BATS_TEST_TMPDIR/custom" DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/custom/alice.key" ]
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
}

@test "postgres script -o writes to the given folder" {
    cd "$WORKDIR"
    DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 -o "$BATS_TEST_TMPDIR/dash-o"
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/dash-o/alice.key" ]
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
    DB_PASSWORD=x PATH="$STUB:$PATH" run env -u HOME -u UUDEX_CERTS "$PG_SCRIPT" --key-size 2048 -o "$BATS_TEST_TMPDIR/nohome"
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/nohome/alice.key" ]
}

@test "postgres script creates the output folder with mode 700" {
    cd "$WORKDIR"
    DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 -o "$BATS_TEST_TMPDIR/private"
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$BATS_TEST_TMPDIR/private")" = "700" ]
}

@test "postgres script refuses an output folder that group or others can write" {
    for m in 775 757 777; do
        mkdir -p "$BATS_TEST_TMPDIR/shared$m"
        chmod "$m" "$BATS_TEST_TMPDIR/shared$m"
        DB_PASSWORD=x PATH="$STUB:$PATH" run "$PG_SCRIPT" --key-size 2048 -o "$BATS_TEST_TMPDIR/shared$m"
        [ "$status" -ne 0 ] || { echo "accepted mode $m"; return 1; }
        [[ "$output" == *"writable"* ]]
        [ -z "$(ls -A "$BATS_TEST_TMPDIR/shared$m")" ]
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
    FAKEBIN="$BATS_TEST_TMPDIR/fakebin"
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
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k "$v" -o "$BATS_TEST_TMPDIR/kv$i"
        echo "key size $v: $output"
        assert_refused_without_files "$BATS_TEST_TMPDIR/kv$i" "--key-size"
        [[ "$output" == *"2048 to 16384"* ]]
    done
}

@test "generate-certs.sh accepts the key size limits 2048 and 16384" {
    cd "$WORKDIR"
    fake_openssl_failing
    local v
    for v in 2048 16384; do
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k "$v" -o "$BATS_TEST_TMPDIR/ok$v"
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
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d "$v" -o "$BATS_TEST_TMPDIR/d$i"
        echo "days $v: $output"
        assert_refused_without_files "$BATS_TEST_TMPDIR/d$i" "--days"
        [[ "$output" == *"1 to 999999"* ]]
    done
}

@test "generate-certs.sh accepts the --days limits 1 and 999999" {
    cd "$WORKDIR"
    fake_openssl_failing
    local v
    for v in 1 999999; do
        PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d "$v" -o "$BATS_TEST_TMPDIR/ok$v"
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
    LC_ALL=en_US.UTF-8 PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k "$wide_key" -o "$BATS_TEST_TMPDIR/wk"
    assert_refused_without_files "$BATS_TEST_TMPDIR/wk" "--key-size"
    LC_ALL=en_US.UTF-8 PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d "$wide_days" -o "$BATS_TEST_TMPDIR/wd"
    assert_refused_without_files "$BATS_TEST_TMPDIR/wd" "--days"
}

@test "generate-certs.sh stops with a named step when openssl fails and leaves no files" {
    cd "$WORKDIR"
    fake_openssl_failing
    PATH="$FAKEBIN:$PATH" run timeout 5 "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/failing"
    [ "$status" -ne 0 ]
    [[ "$output" == *"step failed: generate CA key"* ]]
    [[ "$output" != *"successfully"* ]]
    [ -z "$(ls -A "$BATS_TEST_TMPDIR/failing")" ]
}

@test "generate-certs.sh names the server key step, once, when only that openssl call fails" {
    cd "$WORKDIR"
    local real_openssl
    real_openssl=$(command -v openssl)
    mkdir -p "$BATS_TEST_TMPDIR/selective"
    printf '#!/bin/sh\ncase "$*" in *localhost.key*) exit 1 ;; esac\nexec %s "$@"\n' "$real_openssl" > "$BATS_TEST_TMPDIR/selective/openssl"
    chmod +x "$BATS_TEST_TMPDIR/selective/openssl"
    PATH="$BATS_TEST_TMPDIR/selective:$PATH" run --separate-stderr timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/srv"
    [ "$status" -ne 0 ]
    [[ "$stderr" == *"step failed: generate server key"* ]]
    [ "$(printf '%s\n' "$stderr" | /usr/bin/grep -c 'step failed')" -eq 1 ]
    [[ "$output" != *"Server certificate generated"* ]]
}

@test "generate-certs.sh reports a failed progress message under its own step, not 'starting up'" {
    [ -w /dev/full ] || skip "/dev/full is not available"
    cd "$WORKDIR"
    run bash -c '"$0" alice -k 2048 -o "$1" 2>&1 >/dev/full' "$GEN_SCRIPT" "$BATS_TEST_TMPDIR/full"
    [ "$status" -ne 0 ]
    [[ "$output" == *"step failed: print progress"* ]]
    [[ "$output" != *"starting up"* ]]
}

@test "generate-certs.sh reports one error when the folder permissions cannot be read" {
    cd "$WORKDIR"
    mkdir -p "$BATS_TEST_TMPDIR/faills"
    printf '#!/bin/sh\nexit 1\n' > "$BATS_TEST_TMPDIR/faills/ls"
    chmod +x "$BATS_TEST_TMPDIR/faills/ls"
    PATH="$BATS_TEST_TMPDIR/faills:$PATH" run --separate-stderr timeout 5 "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/lsdir"
    [ "$status" -ne 0 ]
    [[ "$stderr" == *"$BATS_TEST_TMPDIR/lsdir"* ]]
    [ "$(printf '%s\n' "$stderr" | /usr/bin/grep -c .)" -eq 1 ]
}

@test "generate-certs.sh --list on a missing folder exits 1 with the reason on stderr and no step failure" {
    cd "$WORKDIR"
    run --separate-stderr timeout 5 "$GEN_SCRIPT" --list -o "$BATS_TEST_TMPDIR/nothere"
    [ "$status" -eq 1 ]
    [[ "$stderr" == *"does not exist"* ]]
    [[ "$stderr" != *"step failed"* ]]
    [[ "$output" != *"step failed"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/nothere" ]
}

@test "generate-certs.sh refuses an existing owned folder it cannot write, naming it" {
    [ "$(id -u)" -ne 0 ] || skip "root can write to a mode 0500 folder"
    cd "$WORKDIR"
    mkdir -p "$BATS_TEST_TMPDIR/readonly"
    chmod 500 "$BATS_TEST_TMPDIR/readonly"
    run timeout 5 "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/readonly"
    chmod 700 "$BATS_TEST_TMPDIR/readonly"
    assert_refused_without_files "$BATS_TEST_TMPDIR/readonly" "$BATS_TEST_TMPDIR/readonly"
    [[ "$output" == *"not writable"* ]]
}

@test "generate-certs.sh refuses each value option given last with no value" {
    cd "$WORKDIR"
    for opt in --domain -c --country -s --state -l --city -d --days -k --key-size -o --output-dir; do
        run timeout 5 "$GEN_SCRIPT" alice "$opt"
        [ "$status" -ne 124 ] || { echo "$opt hung"; return 1; }
        [ "$status" -ne 0 ] || { echo "$opt accepted with no value"; return 1; }
        [[ "$output" == *"$opt requires a value"* ]] || { echo "$opt: $output"; return 1; }
    done
}

@test "generate-certs.sh refuses a value option followed by another option or an empty value" {
    cd "$WORKDIR"
    run timeout 5 "$GEN_SCRIPT" alice --domain --server-only -o "$BATS_TEST_TMPDIR/dd"
    [ "$status" -ne 0 ]
    [ "$status" -ne 124 ]
    [[ "$output" == *"--domain requires a value"* ]]
    run timeout 5 "$GEN_SCRIPT" alice -o -k 2048
    [ "$status" -ne 0 ]
    [ "$status" -ne 124 ]
    [[ "$output" == *"-o requires a value"* ]]
    run timeout 5 "$GEN_SCRIPT" alice -s "" -o "$BATS_TEST_TMPDIR/empty"
    [ "$status" -ne 0 ]
    [[ "$output" == *"-s requires a value"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/empty" ]
    run timeout 5 "$GEN_SCRIPT" alice -k 2048 -d -5 -o "$BATS_TEST_TMPDIR/negdays"
    [ "$status" -ne 0 ]
    [[ "$output" == *"-d requires a value, got the option-like '-5'"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/negdays" ]
}

@test "generate-certs.sh refuses a blank value for each value option and writes nothing" {
    cd "$WORKDIR"
    fake_openssl_failing
    local opt blank
    for opt in --domain -c -s -l -d -k -o; do
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
    CONF="$BATS_TEST_TMPDIR/test.conf"
    printf '%s\n' "$@" > "$CONF"
    chmod 600 "$CONF"
}

FULL_CONF=(
    "C = CA" "ST = Ontario" "L = Toronto" "O = Conf Org" "CA_CN = Conf CA"
    "KEY_SIZE = 2048" "DAYS = 30" "DOMAINS = conf.example, 10.1.2.3"
)

@test "config: built-in defaults apply with no config file" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -eq 0 ]
    [ "$(subject_of "$BATS_TEST_TMPDIR/o/ca.crt")" = "subject=CN=LocalCA,O=Organization,L=City,ST=State,C=US" ]
}

@test "config: a partial config sets its own keys and the rest stay built-in" {
    cd "$WORKDIR"
    write_conf "O = Partial Org"
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -eq 0 ]
    [ "$(subject_of "$BATS_TEST_TMPDIR/o/ca.crt")" = "subject=CN=LocalCA,O=Partial Org,L=City,ST=State,C=US" ]
}

@test "config: values from the config are used when no option is given" {
    cd "$WORKDIR"
    write_conf "${FULL_CONF[@]}" "OUTPUT_DIR = $BATS_TEST_TMPDIR/cfgout"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -eq 0 ]
    local d="$BATS_TEST_TMPDIR/cfgout"
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
    UUDEX_CERTS_CONF="$CONF" run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -eq 0 ]
    [[ "$(subject_of "$BATS_TEST_TMPDIR/o/ca.crt")" == *"O=Env Conf Org"* ]]
}

@test "config: every option overrides the config value" {
    cd "$WORKDIR"
    write_conf "${FULL_CONF[@]}" "OUTPUT_DIR = $BATS_TEST_TMPDIR/cfgout"
    sed -i 's/^KEY_SIZE = 2048/KEY_SIZE = 2560/' "$CONF"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -c US -s Washington -l Richland \
        --org "Opt Org" --ca-name "Opt CA" -k 2048 -d 400 --domain opt.example -o "$BATS_TEST_TMPDIR/optout"
    [ "$status" -eq 0 ]
    local d="$BATS_TEST_TMPDIR/optout"
    [ ! -e "$BATS_TEST_TMPDIR/cfgout" ]
    [ "$(subject_of "$d/ca.crt")" = "subject=CN=Opt CA,O=Opt Org,L=Richland,ST=Washington,C=US" ]
    [ "$(subject_of "$d/alice.crt")" = "subject=CN=alice,O=Opt Org,L=Richland,ST=Washington,C=US" ]
    [ "$(subject_of "$d/server.crt")" = "subject=CN=opt.example,O=Opt Org,L=Richland,ST=Washington,C=US" ]
    ! openssl x509 -in "$d/server.crt" -noout -ext subjectAltName | /usr/bin/grep -q 'conf.example'
    openssl x509 -in "$d/alice.crt" -noout -text | /usr/bin/grep -q 'Public-Key: (2048 bit)'
    openssl x509 -in "$d/alice.crt" -noout -checkend $((399 * 86400))
}

@test "config: UUDEX_CERTS beats OUTPUT_DIR in the config" {
    cd "$WORKDIR"
    write_conf "OUTPUT_DIR = $BATS_TEST_TMPDIR/cfgout" "KEY_SIZE = 2048"
    UUDEX_CERTS="$BATS_TEST_TMPDIR/envout" run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/envout/alice.key" ]
    [ ! -e "$BATS_TEST_TMPDIR/cfgout" ]
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
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"$CONF line 4: unknown key 'COUNTY'"* ]]
    [[ "$output" != *"successfully"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/o" ]
}

@test "config: a malformed line, a duplicate key and CRLF endings are refused naming the line" {
    cd "$WORKDIR"
    write_conf "C = US" "this is not a setting"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: expected KEY = VALUE"* ]]
    write_conf "C = US" "C = CA"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: key 'C' is set twice"* ]]
    printf 'C = US\r\n' > "$CONF"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 1: carriage return"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/o" ]
}

@test "config: bad KEY_SIZE and DAYS fail with the same range message and the line, even when overridden" {
    cd "$WORKDIR"
    write_conf "C = US" "KEY_SIZE = 1024"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: KEY_SIZE must be a whole number from 2048 to 16384, got '1024'"* ]]
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -k 2048 -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 2: KEY_SIZE"* ]]
    write_conf "DAYS = 1.5"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"line 1: DAYS must be a whole number from 1 to 999999, got '1.5'"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/o" ]
}

@test "config: a blank, option-like or empty-item value is refused like the option form" {
    cd "$WORKDIR"
    local bad
    for bad in "ST =" "ST = -x" "DOMAINS = a.example,,b.example" "DOMAINS = a.example," "O = -"; do
        write_conf "$bad"
        run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
        [ "$status" -ne 0 ] || { echo "accepted: $bad"; return 1; }
        [[ "$output" == *"line 1"* && "$output" == *"requires a value"* ]] || { echo "$bad: $output"; return 1; }
    done
    [ ! -e "$BATS_TEST_TMPDIR/o" ]
}

@test "config: an explicit config that does not exist is refused, a missing default is fine" {
    cd "$WORKDIR"
    run timeout 60 "$GEN_SCRIPT" alice --config "$BATS_TEST_TMPDIR/nothere.conf" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"nothere.conf does not exist"* ]]
    UUDEX_CERTS_CONF="$BATS_TEST_TMPDIR/nothere.conf" run timeout 60 "$GEN_SCRIPT" alice -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"does not exist"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/o" ]
    [ ! -e "$FAKE_HOME/.config/uudex/certs.conf" ]
    run timeout 60 "$GEN_SCRIPT" alice -k 2048 -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -eq 0 ]
}

@test "config: a directory, or a file others can write, is refused and nothing is written" {
    cd "$WORKDIR"
    mkdir "$BATS_TEST_TMPDIR/dir.conf"
    run timeout 60 "$GEN_SCRIPT" alice --config "$BATS_TEST_TMPDIR/dir.conf" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"is not a regular file"* ]]
    write_conf "C = US"
    chmod 666 "$CONF"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -o "$BATS_TEST_TMPDIR/o"
    [ "$status" -ne 0 ]
    [[ "$output" == *"writable by other users"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/o" ]
}

@test "config: a config that is never executed (shell syntax is a malformed line)" {
    cd "$WORKDIR"
    write_conf 'C=$(touch '"$BATS_TEST_TMPDIR"'/pwned)'
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF" -k 2048 -o "$BATS_TEST_TMPDIR/o"
    [ ! -e "$BATS_TEST_TMPDIR/pwned" ]
}

@test "config: with every value in the config, a client name alone makes the CA, server and client certificates" {
    cd "$WORKDIR"
    write_conf "${FULL_CONF[@]}"
    cp "$CONF" "$BATS_TEST_TMPDIR/keep.conf"
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
    ! /usr/bin/grep -qi 'raven2' "$EXAMPLE_CONF"
}

@test "config: --list uses OUTPUT_DIR from the config" {
    cd "$WORKDIR"
    write_conf "OUTPUT_DIR = $BATS_TEST_TMPDIR/listdir" "KEY_SIZE = 2048"
    run timeout 60 "$GEN_SCRIPT" alice --config "$CONF"
    [ "$status" -eq 0 ]
    run timeout 60 "$GEN_SCRIPT" --list --config "$CONF"
    [ "$status" -eq 0 ]
    [[ "$output" == *"$BATS_TEST_TMPDIR/listdir"* && "$output" == *"Name: alice"* ]]
}
