#!/usr/bin/env bats

SCRIPTS="$BATS_TEST_DIRNAME/.."
REPO_ROOT="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"

setup() {
    FAKE_HOME="$BATS_TEST_TMPDIR/home"
    WORKDIR="$BATS_TEST_TMPDIR/work"
    mkdir -p "$FAKE_HOME" "$WORKDIR"
    export HOME="$FAKE_HOME"
    unset UUDEX_CERTS DB_PASSWORD
}

@test "generate-certs.sh writes to ~/.config/uudex/tls by default and not to the working directory" {
    cd "$WORKDIR"
    run "$SCRIPTS/generate-certs.sh" alice -k 2048
    [ "$status" -eq 0 ]
    [ -s "$FAKE_HOME/.config/uudex/tls/ca.crt" ]
    [ -s "$FAKE_HOME/.config/uudex/tls/alice.key" ]
    [ -s "$FAKE_HOME/.config/uudex/tls/alice.crt" ]
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "generate-certs.sh honours UUDEX_CERTS and leaves the default location empty" {
    cd "$WORKDIR"
    UUDEX_CERTS="$BATS_TEST_TMPDIR/custom" run "$SCRIPTS/generate-certs.sh" alice -k 2048
    [ "$status" -eq 0 ]
    [ -s "$BATS_TEST_TMPDIR/custom/alice.key" ]
    [ ! -e "$FAKE_HOME/.config/uudex/tls" ]
}

@test "generate-certs.sh refuses when neither HOME nor UUDEX_CERTS is set" {
    cd "$WORKDIR"
    run env -u HOME -u UUDEX_CERTS "$SCRIPTS/generate-certs.sh" alice -k 2048
    [ "$status" -ne 0 ]
    [[ "$output" == *"UUDEX_CERTS"* ]]
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "postgres script help shows the home-based default output directory" {
    run "$SCRIPTS/generate-certs-from-existing-postgres.sh" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"$FAKE_HOME/.config/uudex/tls"* ]]
}

@test "postgres script refuses to run without a database password and never calls psql" {
    mkdir -p "$BATS_TEST_TMPDIR/stub"
    printf '#!/bin/sh\necho called >> "%s/psql.log"\nexit 0\n' "$BATS_TEST_TMPDIR" > "$BATS_TEST_TMPDIR/stub/psql"
    chmod +x "$BATS_TEST_TMPDIR/stub/psql"
    cd "$WORKDIR"
    PATH="$BATS_TEST_TMPDIR/stub:$PATH" run "$SCRIPTS/generate-certs-from-existing-postgres.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"DB_PASSWORD"* ]]
    [ ! -e "$BATS_TEST_TMPDIR/psql.log" ]
    [ -z "$(ls -A "$WORKDIR")" ]
}

@test "postgres script has no literal default database password" {
    run /usr/bin/grep -nE 'DB_PASSWORD="\$\{DB_PASSWORD:-[^}]' "$SCRIPTS/generate-certs-from-existing-postgres.sh"
    [ "$status" -eq 1 ]
}

@test "gitignore ignores key and certificate files anywhere in the repository" {
    cd "$REPO_ROOT"
    for p in infrastructure/certs/certs/ca.key infrastructure/certs/certs/x.crt infrastructure/certs/x.p12 \
             some.pem some.key tls/a.csr deep/er/dir/x.pfx; do
        run git check-ignore -q "$p"
        [ "$status" -eq 0 ] || { echo "not ignored: $p"; return 1; }
    done
}

@test "gitignore ignores the certs output folder at any depth" {
    cd "$REPO_ROOT"
    run git check-ignore -q infrastructure/certs/certs/readme.txt
    [ "$status" -eq 0 ]
}

@test "gitignore does not hide new files next to the scripts" {
    cd "$REPO_ROOT"
    run git check-ignore -q infrastructure/certs/README.md
    [ "$status" -eq 1 ]
}
