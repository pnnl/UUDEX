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
    unset UUDEX_CERTS DB_PASSWORD

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
