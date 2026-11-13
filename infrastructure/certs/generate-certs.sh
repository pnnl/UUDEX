#!/bin/bash
# Development-only helper. The certificates it makes are examples, not for real deployment.

# -E so the ERR trap also fires inside functions. STEP names what was running
# when a command failed.
set -Eeuo pipefail
STEP="starting up"
trap 'echo "Error: step failed: $STEP (exit status $?)" >&2' ERR

# Default values
DEFAULT_CLIENT_NAME="client"
DEFAULT_ORG="Organization"
DEFAULT_CA_NAME="LocalCA"
DEFAULT_COUNTRY="US"
DEFAULT_STATE="State"
DEFAULT_CITY="City"
DEFAULT_DAYS="365"
DEFAULT_KEY_SIZE="4096"
DEFAULT_CERTS_REL=".config/uudex/tls"
DEFAULT_CONFIG_REL=".config/uudex/certs.conf"
DEFAULT_CERTS_DIR="\$HOME/$DEFAULT_CERTS_REL"
DEFAULT_CONFIG_FILE="\$HOME/$DEFAULT_CONFIG_REL"

# Output directory: -o, then UUDEX_CERTS, then OUTPUT_DIR in the config, then
# the home-based default. Keys must never land in a working tree, so there is
# no relative default. An empty value is resolved after argument parsing, so
# --help and -o work without HOME.
CERTS_DIR="${UUDEX_CERTS:-}"

resolve_certs_dir() {
    if [ -z "$CERTS_DIR" ] && [ -n "$CFG_OUTPUT_DIR" ]; then
        CERTS_DIR="$CFG_OUTPUT_DIR"
    fi
    if [ -z "$CERTS_DIR" ]; then
        if [ -z "${HOME:-}" ]; then
            echo "Error: HOME is not set; set UUDEX_CERTS or pass --output-dir" >&2
            exit 1
        fi
        CERTS_DIR="$HOME/$DEFAULT_CERTS_REL"
    fi
}

# Keys go in this folder, so refuse one that others can write or that another
# user owns: an existing ca.key there would be reused and a planted symlink
# would be followed.
prepare_certs_dir() {
    (umask 077 && mkdir -p "$CERTS_DIR") || {
        echo "Error: cannot create output folder $CERTS_DIR" >&2
        exit 1
    }
    if [ ! -d "$CERTS_DIR" ] || [ ! -O "$CERTS_DIR" ]; then
        echo "Error: output folder $CERTS_DIR must be a directory owned by you" >&2
        exit 1
    fi
    local mode
    mode=$(ls -ldL "$CERTS_DIR") || {
        echo "Error: cannot read the permissions of output folder $CERTS_DIR" >&2
        exit 1
    }
    if [ ! -w "$CERTS_DIR" ] || [ ! -x "$CERTS_DIR" ]; then
        echo "Error: output folder $CERTS_DIR is not writable by you; fix its permissions or choose another" >&2
        exit 1
    fi
    if [ "${mode:5:1}" = "w" ] || [ "${mode:8:1}" = "w" ]; then
        echo "Error: output folder $CERTS_DIR is writable by other users; run chmod go-w on it or choose another" >&2
        exit 1
    fi
}

# A value, from an option or from the config file, must not be blank or
# option-like. label names where it came from.
check_value() {
    local label="$1" value="$2"
    if [ -z "$value" ]; then
        echo "Error: $label requires a value" >&2
        exit 1
    fi
    if [[ "$value" =~ ^[[:space:]]+$ ]]; then
        echo "Error: $label requires a value that is not blank" >&2
        exit 1
    fi
    if [[ "$value" == -* ]]; then
        echo "Error: $label requires a value, got the option-like '$value'" >&2
        exit 1
    fi
}

need_value() {
    local opt="$1" argc="$2" value="$3"
    if [ "$argc" -lt 2 ]; then
        echo "Error: $opt requires a value" >&2
        exit 1
    fi
    check_value "$opt" "$value"
}

KEY_SIZE_MIN=2048
KEY_SIZE_MAX=16384

# Checked before any file is written: openssl accepts some bad values and
# fails on others, and the failure used to be reported as success. Digits are
# spelled out because [0-9] also matches full-width digits in some UTF-8
# locales, which then pass the pattern and break the arithmetic test.
check_key_size() {
    local label="$1" value="$2"
    local digit='[0123456789]' lead='[123456789]'
    local key_re="^$lead$digit{3,4}\$"
    if ! [[ "$value" =~ $key_re ]] || [ "$value" -lt "$KEY_SIZE_MIN" ] || [ "$value" -gt "$KEY_SIZE_MAX" ]; then
        echo "Error: $label must be a whole number from $KEY_SIZE_MIN to $KEY_SIZE_MAX, got '$value'" >&2
        exit 1
    fi
}

check_days() {
    local label="$1" value="$2"
    local digit='[0123456789]' lead='[123456789]'
    local days_re="^$lead$digit{0,5}\$"
    if ! [[ "$value" =~ $days_re ]]; then
        echo "Error: $label must be a whole number from 1 to 999999, got '$value'" >&2
        exit 1
    fi
}

# These values are placed in an openssl -subj string and in a generated openssl
# config. In -subj, / starts a field, \ escapes and + makes a multi-valued
# name; in the config, # starts a comment, $ expands, quotes group and \
# escapes. Each would make the CA, server and client subjects differ or add
# fields. = , ; & % : @ [ ] pass through unchanged and are allowed.
check_subject_value() {
    local label="$1" value="$2"
    local bad_re='[/\#$"'"'"'+[:cntrl:]]'
    if [[ "$value" =~ $bad_re ]]; then
        if [[ "${BASH_REMATCH[0]}" == [[:cntrl:]] ]]; then
            echo "Error: $label contains a control character, which openssl would misread in a certificate subject" >&2
        else
            echo "Error: $label contains the character '${BASH_REMATCH[0]}', which openssl would misread in a certificate subject" >&2
        fi
        exit 1
    fi
}

IPV4_RE='^[0123456789]{1,3}(\.[0123456789]{1,3}){3}$'

# Each field is 1 to 4 hex digits; "::" stands for one or more zero fields and
# may appear once. Dotted-quad tails are not accepted.
is_ipv6() {
    local v="$1" head tail group count
    local -a fields=() tail_fields=()
    [[ "$v" =~ ^[0123456789abcdefABCDEF:]+$ ]] || return 1
    [[ "$v" == *:::* || "$v" == *::*::* ]] && return 1
    [[ "$v" == :* && "$v" != ::* ]] && return 1
    [[ "$v" == *: && "$v" != *:: ]] && return 1
    if [[ "$v" == *::* ]]; then
        head="${v%%::*}"
        tail="${v#*::}"
        IFS=: read -ra fields <<< "$head"
        IFS=: read -ra tail_fields <<< "$tail"
        fields+=("${tail_fields[@]+"${tail_fields[@]}"}")
        count=${#fields[@]}
        [ "$count" -le 7 ] || return 1
    else
        IFS=: read -ra fields <<< "$v"
        count=${#fields[@]}
        [ "$count" -eq 8 ] || return 1
    fi
    for group in "${fields[@]+"${fields[@]}"}"; do
        [[ "$group" =~ ^[0123456789abcdefABCDEF]{1,4}$ ]] || return 1
    done
}

# A server name must be a DNS name, a dotted IPv4 address or an IPv6 address.
# It is written into the server request config as CN and a SAN entry, so the
# allowed characters are listed rather than the bad ones.
check_domain() {
    local label="$1" value="$2" octet
    local dns_re='^[ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789*_.-]+$'
    if [[ "$value" == *:* ]]; then
        is_ipv6 "$value" || {
            echo "Error: $label '$value' is not a valid IPv6 address" >&2
            exit 1
        }
        return 0
    fi
    if ! [[ "$value" =~ $dns_re ]]; then
        echo "Error: $label '$value' is not a DNS name or IP address (letters, digits, '.', '-', '_' and '*' only)" >&2
        exit 1
    fi
    if [[ "$value" =~ $IPV4_RE ]]; then
        local -a octets
        IFS=. read -ra octets <<< "$value"
        for octet in "${octets[@]}"; do
            if [[ "$octet" =~ ^0[0123456789] ]] || [ "$octet" -gt 255 ]; then
                echo "Error: $label '$value' is not a valid IPv4 address (octets are 0 to 255 without leading zeros)" >&2
                exit 1
            fi
        done
    fi
}

CONFIG_FILE=""
CFG_COUNTRY="" CFG_STATE="" CFG_CITY="" CFG_ORG="" CFG_CA_NAME=""
CFG_KEY_SIZE="" CFG_DAYS="" CFG_OUTPUT_DIR=""
CFG_DOMAINS=()

config_fail() {
    echo "Error: config file $CONFIG_FILE $1" >&2
    exit 1
}

trim() {
    local s="$1"
    s="${s#"${s%%[![:space:]]*}"}"
    printf '%s' "${s%"${s##*[![:space:]]}"}"
}

# The file is parsed, never sourced: it holds KEY = VALUE lines and nothing in
# it is executed. Every value passes the checks its command-line twin does.
parse_config() {
    local lineno=0 line key value seen=" " label item rest
    local line_re='^([A-Za-z_]+)[[:space:]]*=[[:space:]]*(.*)$'
    while IFS= read -r line || [ -n "$line" ]; do
        lineno=$((lineno + 1))
        if [[ "$line" == *$'\r'* ]]; then
            config_fail "line $lineno: carriage return found; use Unix line endings"
        fi
        line=$(trim "$line")
        if [ -z "$line" ] || [[ "$line" == \#* ]]; then
            continue
        fi
        if ! [[ "$line" =~ $line_re ]]; then
            config_fail "line $lineno: expected KEY = VALUE, got '$line'"
        fi
        key="${BASH_REMATCH[1]}"
        value=$(trim "${BASH_REMATCH[2]}")
        label="config file $CONFIG_FILE line $lineno: $key"
        case "$key" in
            C|ST|L|O|CA_CN|KEY_SIZE|DAYS|DOMAINS|OUTPUT_DIR) ;;
            *) config_fail "line $lineno: unknown key '$key' (known: C ST L O CA_CN KEY_SIZE DAYS DOMAINS OUTPUT_DIR)" ;;
        esac
        if [[ "$seen" == *" $key "* ]]; then
            config_fail "line $lineno: key '$key' is set twice"
        fi
        seen="$seen$key "
        check_value "$label" "$value"
        case "$key" in
            C) check_subject_value "$label" "$value"; CFG_COUNTRY="$value" ;;
            ST) check_subject_value "$label" "$value"; CFG_STATE="$value" ;;
            L) check_subject_value "$label" "$value"; CFG_CITY="$value" ;;
            O) check_subject_value "$label" "$value"; CFG_ORG="$value" ;;
            CA_CN) check_subject_value "$label" "$value"; CFG_CA_NAME="$value" ;;
            KEY_SIZE)
                check_key_size "$label" "$value"
                CFG_KEY_SIZE="$value"
                ;;
            DAYS)
                check_days "$label" "$value"
                CFG_DAYS="$value"
                ;;
            DOMAINS)
                rest="$value"
                while :; do
                    item=$(trim "${rest%%,*}")
                    check_value "$label" "$item"
                    check_domain "$label" "$item"
                    CFG_DOMAINS+=("$item")
                    [[ "$rest" == *,* ]] || break
                    rest="${rest#*,}"
                done
                ;;
            OUTPUT_DIR)
                if [[ "$value" == \~/* ]]; then
                    if [ -z "${HOME:-}" ]; then
                        config_fail "line $lineno: OUTPUT_DIR uses ~ but HOME is not set"
                    fi
                    value="$HOME/${value#\~/}"
                fi
                if [[ "$value" != /* ]]; then
                    config_fail "line $lineno: OUTPUT_DIR must be an absolute path or start with ~/, got '$value'"
                fi
                CFG_OUTPUT_DIR="$value"
                ;;
        esac
    done < "$CONFIG_FILE"
}

# An explicit path (--config or UUDEX_CERTS_CONF) must exist; an empty
# UUDEX_CERTS_CONF is refused rather than read as unset. The default path may be
# absent, but a default that exists and cannot be used is an error. A config
# others can write could redirect the output folder or the domains.
load_config() {
    local explicit=true mode
    if [ -z "$CONFIG_FILE" ] && [ "${UUDEX_CERTS_CONF+set}" = set ]; then
        check_value "UUDEX_CERTS_CONF" "$UUDEX_CERTS_CONF"
        CONFIG_FILE="$UUDEX_CERTS_CONF"
    fi
    if [ -z "$CONFIG_FILE" ]; then
        explicit=false
        if [ -z "${HOME:-}" ]; then
            return 0
        fi
        CONFIG_FILE="$HOME/$DEFAULT_CONFIG_REL"
        if [ ! -e "$CONFIG_FILE" ] && [ ! -L "$CONFIG_FILE" ]; then
            return 0
        fi
    fi
    if [ ! -f "$CONFIG_FILE" ]; then
        if [ "$explicit" = true ] && [ ! -e "$CONFIG_FILE" ]; then
            config_fail "does not exist"
        fi
        config_fail "is not a regular file"
    fi
    if [ ! -r "$CONFIG_FILE" ] || [ ! -O "$CONFIG_FILE" ]; then
        config_fail "must be readable and owned by you"
    fi
    mode=$(ls -ldL "$CONFIG_FILE") || config_fail "permissions cannot be read"
    if [ "${mode:5:1}" = "w" ] || [ "${mode:8:1}" = "w" ]; then
        config_fail "is writable by other users; run chmod go-w on it"
    fi
    parse_config
}

# Function to display help
show_help() {
    echo "Usage: $0 [CLIENT_NAME] [ORG] [OPTIONS]"
    echo ""
    echo "Generate client certificates signed by a shared CA"
    echo ""
    echo "Positional arguments:"
    echo "  CLIENT_NAME         Name for the client certificate (default: $DEFAULT_CLIENT_NAME)"
    echo "  ORG                 Organization name (config key O, default: $DEFAULT_ORG)"
    echo ""
    echo "Nothing is required. Precedence: command line, then config file, then built-in default."
    echo ""
    echo "Options:"
    echo "  -c, --country CODE  Country code (default: $DEFAULT_COUNTRY)"
    echo "  -s, --state STATE   State or province (default: $DEFAULT_STATE)"
    echo "  -l, --city CITY     City or locality (default: $DEFAULT_CITY)"
    echo "  -d, --days DAYS     Certificate validity in days (default: $DEFAULT_DAYS)"
    echo "  -k, --key-size SIZE RSA key size in bits (default: $DEFAULT_KEY_SIZE)"
    echo "  -o, --output-dir DIR Output directory for certificates (overrides UUDEX_CERTS and OUTPUT_DIR)"
    echo "  --org ORG           Organization name (same as the ORG argument)"
    echo "  --ca-name NAME      CA common name (default: $DEFAULT_CA_NAME)"
    echo "  --config FILE       Read defaults from FILE (default: $DEFAULT_CONFIG_FILE, if it exists)"
    echo "  --domain DOMAIN     Add domain to server certificate (can be used multiple times)"
    echo "  --server-only       Generate only server certificate with specified domains"
    echo "  --list              List existing certificates in the output directory"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  UUDEX_CERTS         Override certificate output directory (overrides OUTPUT_DIR; default: $DEFAULT_CERTS_DIR)"
    echo "  UUDEX_CERTS_CONF    Config file to read instead of $DEFAULT_CONFIG_FILE"
    echo ""
    echo "Config file: KEY = VALUE lines; keys C ST L O CA_CN KEY_SIZE DAYS DOMAINS OUTPUT_DIR."
    echo "  OUTPUT_DIR sets the output directory when -o and UUDEX_CERTS are not given."
    echo "See uudex-certs.conf.example next to this script."
    echo ""
    echo "Examples:"
    echo "  $0                              # Generate certificate for 'client'"
    echo "  $0 alice                        # Generate certificate for 'alice'"
    echo "  $0 bob \"Acme Corp\"              # Generate certificate for 'bob' at 'Acme Corp'"
    echo "  $0 alice \"Acme\" --days 730      # Generate 2-year certificate for 'alice'"
    echo "  $0 bob \"Corp\" -c CA -s Ontario  # Generate certificate with Canadian details"
    echo "  $0 alice --output-dir /custom/path # Output certificates to /custom/path"
    echo "  $0 --list                       # List existing certificates"
    echo ""
    echo "Server certificate examples:"
    echo "  $0 --server-only \"Acme Corp\" --domain localhost --domain api.example.com"
    echo "  $0 --server-only \"My Org\" --domain *.example.com --domain example.com"
    echo "  $0 alice \"Corp\" --domain localhost --domain api.local  # Generate client + server with domains"
}

# Function to list certificates
list_certificates() {
    STEP="list certificates"
    if [ ! -d "$CERTS_DIR" ]; then
        echo "Error: directory does not exist: $CERTS_DIR" >&2
        exit 1
    fi

    echo "Certificates in directory: $CERTS_DIR"
    echo "=================================================="

    local found_certs=false

    # Check for CA certificate
    if [ -f "$CERTS_DIR/ca.crt" ]; then
        echo "CA Certificate:"
        echo "  File: $CERTS_DIR/ca.crt"
        echo "  Subject: $(openssl x509 -in "$CERTS_DIR/ca.crt" -noout -subject 2>/dev/null || echo "Unable to read")"
        echo "  Valid until: $(openssl x509 -in "$CERTS_DIR/ca.crt" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "Unknown")"
        echo ""
        found_certs=true
    fi

    # List client certificates
    echo "Client Certificates:"
    for cert_file in "$CERTS_DIR"/*.crt; do
        if [ -f "$cert_file" ] && [ "$(basename "$cert_file")" != "ca.crt" ] && [ "$(basename "$cert_file")" != "ca-trusted.crt" ]; then
            local cert_name=$(basename "$cert_file" .crt)
            echo "  Name: $cert_name"
            echo "  Certificate: $cert_file"
            echo "  Private Key: $CERTS_DIR/${cert_name}.key"
            echo "  PKCS#12: $CERTS_DIR/${cert_name}.p12"
            echo "  Subject: $(openssl x509 -in "$cert_file" -noout -subject 2>/dev/null || echo "Unable to read")"
            echo "  Valid until: $(openssl x509 -in "$cert_file" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "Unknown")"
            echo ""
            found_certs=true
        fi
    done

    if [ "$found_certs" = false ]; then
        echo "No certificates found in $CERTS_DIR"
    fi
}

# Initialize variables
CLIENT_NAME=""
ORG=""
COUNTRY=""
STATE=""
CITY=""
CA_NAME=""
DAYS=""
KEY_SIZE=""
LIST_CERTS=false
SERVER_ONLY=false
DOMAINS=()  # Array to store multiple domains

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --list)
            LIST_CERTS=true
            shift
            ;;
        --server-only)
            SERVER_ONLY=true
            shift
            ;;
        --domain)
            need_value "$1" "$#" "${2-}"
            DOMAINS+=("$2")
            shift 2
            ;;
        -c|--country)
            need_value "$1" "$#" "${2-}"
            COUNTRY="$2"
            shift 2
            ;;
        -s|--state)
            need_value "$1" "$#" "${2-}"
            STATE="$2"
            shift 2
            ;;
        -l|--city)
            need_value "$1" "$#" "${2-}"
            CITY="$2"
            shift 2
            ;;
        -d|--days)
            need_value "$1" "$#" "${2-}"
            DAYS="$2"
            shift 2
            ;;
        -k|--key-size)
            need_value "$1" "$#" "${2-}"
            KEY_SIZE="$2"
            shift 2
            ;;
        --org)
            need_value "$1" "$#" "${2-}"
            ORG="$2"
            shift 2
            ;;
        --ca-name)
            need_value "$1" "$#" "${2-}"
            CA_NAME="$2"
            shift 2
            ;;
        --config)
            need_value "$1" "$#" "${2-}"
            CONFIG_FILE="$2"
            shift 2
            ;;
        -o|--output-dir)
            need_value "$1" "$#" "${2-}"
            CERTS_DIR="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1" >&2
            show_help
            exit 1
            ;;
        *)
            if [[ -z "$CLIENT_NAME" ]]; then
                CLIENT_NAME="$1"
            elif [[ -z "$ORG" ]]; then
                ORG="$1"
            else
                echo "Too many positional arguments" >&2
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# Every value from the command line is checked before any file is read or written.
check_subject_value "--country" "$COUNTRY"
check_subject_value "--state" "$STATE"
check_subject_value "--city" "$CITY"
check_subject_value "ORG (second argument or --org)" "$ORG"
check_subject_value "--ca-name" "$CA_NAME"
check_subject_value "CLIENT_NAME" "$CLIENT_NAME"
for domain in "${DOMAINS[@]+"${DOMAINS[@]}"}"; do
    check_domain "--domain" "$domain"
done

load_config
resolve_certs_dir

# If list option is specified, list certificates and exit
if [ "$LIST_CERTS" = true ]; then
    list_certificates
    exit 0
fi

# Command line wins, then the config file, then the built-in default.
apply_config_and_defaults() {
    : "${COUNTRY:=${CFG_COUNTRY:-$DEFAULT_COUNTRY}}"
    : "${STATE:=${CFG_STATE:-$DEFAULT_STATE}}"
    : "${CITY:=${CFG_CITY:-$DEFAULT_CITY}}"
    : "${ORG:=${CFG_ORG:-$DEFAULT_ORG}}"
    : "${CA_NAME:=${CFG_CA_NAME:-$DEFAULT_CA_NAME}}"
    : "${KEY_SIZE:=${CFG_KEY_SIZE:-$DEFAULT_KEY_SIZE}}"
    : "${DAYS:=${CFG_DAYS:-$DEFAULT_DAYS}}"
    if [ ${#DOMAINS[@]} -eq 0 ] && [ ${#CFG_DOMAINS[@]} -gt 0 ]; then
        DOMAINS=("${CFG_DOMAINS[@]}")
    fi
}

# Handle server-only mode
if [ "$SERVER_ONLY" = true ]; then
    # For server-only mode, we need ORG but not CLIENT_NAME
    if [[ -z "$ORG" ]] && [[ -n "$CLIENT_NAME" ]]; then
        # If CLIENT_NAME is provided but not ORG, treat CLIENT_NAME as ORG
        ORG="$CLIENT_NAME"
        CLIENT_NAME=""
    fi
    apply_config_and_defaults

    # Require at least one domain for server-only mode
    if [ ${#DOMAINS[@]} -eq 0 ]; then
        echo "Error: --server-only requires at least one --domain (or DOMAINS in the config file)" >&2
        echo "Example: $0 --server-only \"My Org\" --domain localhost --domain api.example.com" >&2
        exit 1
    fi
else
    # Set defaults for normal mode (client certificate generation)
    CLIENT_NAME="${CLIENT_NAME:-$DEFAULT_CLIENT_NAME}"
    apply_config_and_defaults

    # If no domains specified, default to localhost
    if [ ${#DOMAINS[@]} -eq 0 ]; then
        DOMAINS=("localhost")
    fi
fi

STEP="validate numbers"
check_key_size "--key-size" "$KEY_SIZE"
check_days "--days" "$DAYS"
STEP="prepare output folder"
prepare_certs_dir

# Generate CA only if it doesn't exist
CA_REUSED=false
if [ ! -f "$CERTS_DIR/ca.key" ] || [ ! -f "$CERTS_DIR/ca.crt" ]; then
    STEP="print progress"
    echo "Generating new CA certificate..."

    STEP="generate CA key"
    openssl genrsa -out "$CERTS_DIR/ca.key" "$KEY_SIZE"

    STEP="generate CA certificate"
    openssl req -new -x509 -days "$DAYS" -key "$CERTS_DIR/ca.key" -out "$CERTS_DIR/ca.crt" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=$CA_NAME"

    STEP="print progress"
    echo "CA certificate generated successfully!"
else
    STEP="print progress"
    echo "Using existing CA certificate..."
    CA_REUSED=true
fi

# The CA subject printed below is read back from ca.crt: an existing CA is
# kept as it is, so the requested values may not be the ones in use.
STEP="read CA subject"
CA_SUBJECT_OPTS="sep_comma_plus_space,dn_rev,sname,utf8"
CA_SUBJECT=$(openssl x509 -in "$CERTS_DIR/ca.crt" -noout -subject -nameopt "$CA_SUBJECT_OPTS") || {
    echo "Error: cannot read the subject of $CERTS_DIR/ca.crt" >&2
    exit 1
}
CA_SUBJECT="${CA_SUBJECT#subject=}"
CA_REQUESTED="CN=$CA_NAME, O=$ORG, L=$CITY, ST=$STATE, C=$COUNTRY"
if [ "$CA_REUSED" = true ] && [ "$CA_SUBJECT" != "$CA_REQUESTED" ]; then
    echo "Warning: the existing CA at $CERTS_DIR/ca.crt has subject '$CA_SUBJECT', not the requested '$CA_REQUESTED'; the existing CA is kept" >&2
fi

# Function to generate server certificate with multiple domains
generate_server_certificate() {
    local domains=("$@")
    local primary_domain="${domains[0]}"
    local cert_name="server"

    # If only localhost, use localhost as filename for backward compatibility
    if [ ${#domains[@]} -eq 1 ] && [ "${domains[0]}" = "localhost" ]; then
        cert_name="localhost"
    fi

    STEP="print progress"
    echo "Generating server certificate for domains: ${domains[*]}"

    STEP="generate server key"
    openssl genrsa -out "$CERTS_DIR/${cert_name}.key" "$KEY_SIZE"

    STEP="write server certificate config"
    local config_file="$CERTS_DIR/${cert_name}.conf"
    cat > "$config_file" << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C=$COUNTRY
ST=$STATE
L=$CITY
O=$ORG
CN=$primary_domain

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
EOF

    # Add all domains as alternative names
    # An IP address in a DNS entry never matches a client that connects by IP.
    local dns_i=1 ip_i=1
    for domain in "${domains[@]}"; do
        if [[ "$domain" == *:* || "$domain" =~ $IPV4_RE ]]; then
            echo "IP.${ip_i} = $domain" >> "$config_file"
            ip_i=$((ip_i + 1))
        else
            echo "DNS.${dns_i} = $domain" >> "$config_file"
            dns_i=$((dns_i + 1))
        fi
    done

    STEP="generate server certificate request"
    openssl req -new -key "$CERTS_DIR/${cert_name}.key" -out "$CERTS_DIR/${cert_name}.csr" -config "$config_file"

    STEP="sign server certificate"
    openssl x509 -req -days "$DAYS" -in "$CERTS_DIR/${cert_name}.csr" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial -out "$CERTS_DIR/${cert_name}.crt" -extensions v3_req -extfile "$config_file"

    STEP="remove server temporary files"
    rm "$CERTS_DIR/${cert_name}.csr" "$config_file"

    STEP="print summary"
    echo "Server certificate generated successfully!"
    echo "  Certificate: $CERTS_DIR/${cert_name}.crt"
    echo "  Private Key: $CERTS_DIR/${cert_name}.key"
    echo "  Domains: ${domains[*]}"
}

# Copy CA certificate to Caddy trusted path (will be mounted in Docker)
STEP="copy CA certificate to ca-trusted.crt"
cp "$CERTS_DIR/ca.crt" "$CERTS_DIR/ca-trusted.crt"

# Generate server certificate with specified domains
# Check if we need to regenerate based on domains or if files don't exist
SERVER_CERT_NAME="server"
if [ ${#DOMAINS[@]} -eq 1 ] && [ "${DOMAINS[0]}" = "localhost" ]; then
    SERVER_CERT_NAME="localhost"
fi

# Always regenerate server certificate if domains are specified or if it doesn't exist
if [ ${#DOMAINS[@]} -gt 0 ] && ([ ! -f "$CERTS_DIR/${SERVER_CERT_NAME}.crt" ] || [ ! -f "$CERTS_DIR/${SERVER_CERT_NAME}.key" ]); then
    generate_server_certificate "${DOMAINS[@]}"
elif [ ${#DOMAINS[@]} -gt 1 ] || ([ ${#DOMAINS[@]} -eq 1 ] && [ "${DOMAINS[0]}" != "localhost" ]); then
    # Regenerate if we have multiple domains or a domain other than localhost
    generate_server_certificate "${DOMAINS[@]}"
elif [ ! -f "$CERTS_DIR/localhost.crt" ] || [ ! -f "$CERTS_DIR/localhost.key" ]; then
    # Fallback to localhost if no domains specified and localhost cert doesn't exist
    generate_server_certificate "localhost"
fi

# If server-only mode, exit here without generating client certificate
if [ "$SERVER_ONLY" = true ]; then
    STEP="print summary"
    echo ""
    echo "Server certificate generation completed!"
    echo "CA Certificate: $CERTS_DIR/ca.crt"
    echo "Server Certificate: $CERTS_DIR/${SERVER_CERT_NAME}.crt"
    echo "Server Private Key: $CERTS_DIR/${SERVER_CERT_NAME}.key"
    echo ""
    echo "Certificate details:"
    echo "  Country: $COUNTRY"
    echo "  State: $STATE"
    echo "  City: $CITY"
    echo "  Organization: $ORG"
    echo "  CA subject: $CA_SUBJECT"
    echo "  Domains: ${DOMAINS[*]}"
    echo "  Valid for: $DAYS days"
    echo "  Key size: $KEY_SIZE bits"
    echo "  Output directory: $CERTS_DIR"
    echo ""
    echo "Test server certificate:"
    echo "  curl --cacert $CERTS_DIR/ca.crt https://${DOMAINS[0]}/"
    exit 0
fi

STEP="generate client key"
openssl genrsa -out "$CERTS_DIR/${CLIENT_NAME}.key" "$KEY_SIZE"

STEP="generate client certificate request"
openssl req -new -key "$CERTS_DIR/${CLIENT_NAME}.key" -out "$CERTS_DIR/${CLIENT_NAME}.csr" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=$CLIENT_NAME"

STEP="sign client certificate"
openssl x509 -req -days "$DAYS" -in "$CERTS_DIR/${CLIENT_NAME}.csr" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial -out "$CERTS_DIR/${CLIENT_NAME}.crt"

STEP="export client PKCS#12 bundle"
openssl pkcs12 -export -out "$CERTS_DIR/${CLIENT_NAME}.p12" -inkey "$CERTS_DIR/${CLIENT_NAME}.key" -in "$CERTS_DIR/${CLIENT_NAME}.crt" -certfile "$CERTS_DIR/ca.crt" -password pass:changeme

STEP="remove client request file"
rm "$CERTS_DIR/${CLIENT_NAME}.csr"

STEP="set file permissions"
chmod 600 "$CERTS_DIR"/*.key
chmod 644 "$CERTS_DIR"/*.crt "$CERTS_DIR"/*.p12

STEP="print summary"
echo "Client certificate generated successfully!"
echo "CA Certificate: $CERTS_DIR/ca.crt"
echo "Server Certificate: $CERTS_DIR/${SERVER_CERT_NAME}.crt"
echo "Server Private Key: $CERTS_DIR/${SERVER_CERT_NAME}.key"
echo "Client Certificate: $CERTS_DIR/${CLIENT_NAME}.crt"
echo "Client Private Key: $CERTS_DIR/${CLIENT_NAME}.key"
echo "Client PKCS#12 (for browsers): $CERTS_DIR/${CLIENT_NAME}.p12 (password: changeme)"
echo ""
echo "Certificate details:"
echo "  Country: $COUNTRY"
echo "  State: $STATE"
echo "  City: $CITY"
echo "  Organization: $ORG"
echo "  CA subject: $CA_SUBJECT"
echo "  Client Name: $CLIENT_NAME"
echo "  Server Domains: ${DOMAINS[*]}"
echo "  Valid for: $DAYS days"
echo "  Key size: $KEY_SIZE bits"
echo "  Output directory: $CERTS_DIR"
echo ""
echo "Test with curl:"
echo "  curl --cacert $CERTS_DIR/ca.crt --cert $CERTS_DIR/${CLIENT_NAME}.crt --key $CERTS_DIR/${CLIENT_NAME}.key https://${DOMAINS[0]}/"
