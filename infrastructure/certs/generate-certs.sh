#!/bin/bash

# Default values
DEFAULT_CLIENT_NAME="client"
DEFAULT_ORG="Organization"
DEFAULT_COUNTRY="US"
DEFAULT_STATE="State"
DEFAULT_CITY="City"
DEFAULT_DAYS="365"
DEFAULT_KEY_SIZE="4096"
DEFAULT_CERTS_DIR="certs"

# Certificate output directory (can be overridden by UUDEX_CERTS environment variable)
CERTS_DIR="${UUDEX_CERTS:-$DEFAULT_CERTS_DIR}"

# Function to display help
show_help() {
    echo "Usage: $0 [CLIENT_NAME] [ORG] [OPTIONS]"
    echo ""
    echo "Generate client certificates signed by a shared CA"
    echo ""
    echo "Positional arguments:"
    echo "  CLIENT_NAME         Name for the client certificate (default: $DEFAULT_CLIENT_NAME)"
    echo "  ORG                 Organization name (default: $DEFAULT_ORG)"
    echo ""
    echo "Options:"
    echo "  -c, --country CODE  Country code (default: $DEFAULT_COUNTRY)"
    echo "  -s, --state STATE   State or province (default: $DEFAULT_STATE)"
    echo "  -l, --city CITY     City or locality (default: $DEFAULT_CITY)"
    echo "  -d, --days DAYS     Certificate validity in days (default: $DEFAULT_DAYS)"
    echo "  -k, --key-size SIZE RSA key size in bits (default: $DEFAULT_KEY_SIZE)"
    echo "  -o, --output-dir DIR Output directory for certificates (overrides UUDEX_CERTS)"
    echo "  --domain DOMAIN     Add domain to server certificate (can be used multiple times)"
    echo "  --server-only       Generate only server certificate with specified domains"
    echo "  --list              List existing certificates in the output directory"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  UUDEX_CERTS         Override certificate output directory (default: $DEFAULT_CERTS_DIR)"
    echo ""
    echo "Examples:"
    echo "  $0                              # Generate certificate for 'client'"
    echo "  $0 alice                        # Generate certificate for 'alice'"
    echo "  $0 bob \"Acme Corp\"              # Generate certificate for 'bob' at 'Acme Corp'"
    echo "  $0 alice \"Acme\" --days 730      # Generate 2-year certificate for 'alice'"
    echo "  $0 bob \"Corp\" -c CA -s Ontario  # Generate certificate with Canadian details"
    echo "  UUDEX_CERTS=/tmp/certs $0 alice  # Output certificates to /tmp/certs"
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
    echo "Certificates in directory: $CERTS_DIR"
    echo "=================================================="

    if [ ! -d "$CERTS_DIR" ]; then
        echo "Directory does not exist: $CERTS_DIR"
        return 1
    fi

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
COUNTRY="$DEFAULT_COUNTRY"
STATE="$DEFAULT_STATE"
CITY="$DEFAULT_CITY"
DAYS="$DEFAULT_DAYS"
KEY_SIZE="$DEFAULT_KEY_SIZE"
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
            DOMAINS+=("$2")
            shift 2
            ;;
        -c|--country)
            COUNTRY="$2"
            shift 2
            ;;
        -s|--state)
            STATE="$2"
            shift 2
            ;;
        -l|--city)
            CITY="$2"
            shift 2
            ;;
        -d|--days)
            DAYS="$2"
            shift 2
            ;;
        -k|--key-size)
            KEY_SIZE="$2"
            shift 2
            ;;
        -o|--output-dir)
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

# If list option is specified, list certificates and exit
if [ "$LIST_CERTS" = true ]; then
    list_certificates
    exit 0
fi

# Handle server-only mode
if [ "$SERVER_ONLY" = true ]; then
    # For server-only mode, we need ORG but not CLIENT_NAME
    if [[ -z "$ORG" ]]; then
        if [[ -n "$CLIENT_NAME" ]]; then
            # If CLIENT_NAME is provided but not ORG, treat CLIENT_NAME as ORG
            ORG="$CLIENT_NAME"
            CLIENT_NAME=""
        else
            ORG="$DEFAULT_ORG"
        fi
    fi

    # Require at least one domain for server-only mode
    if [ ${#DOMAINS[@]} -eq 0 ]; then
        echo "Error: --server-only requires at least one --domain specification" >&2
        echo "Example: $0 --server-only \"My Org\" --domain localhost --domain api.example.com" >&2
        exit 1
    fi
else
    # Set defaults for normal mode (client certificate generation)
    CLIENT_NAME="${CLIENT_NAME:-$DEFAULT_CLIENT_NAME}"
    ORG="${ORG:-$DEFAULT_ORG}"

    # If no domains specified, default to localhost
    if [ ${#DOMAINS[@]} -eq 0 ]; then
        DOMAINS=("localhost")
    fi
fi

# Create certs directory
mkdir -p "$CERTS_DIR"

# Generate CA only if it doesn't exist
if [ ! -f "$CERTS_DIR/ca.key" ] || [ ! -f "$CERTS_DIR/ca.crt" ]; then
    echo "Generating new CA certificate..."

    # Generate CA private key
    openssl genrsa -out "$CERTS_DIR/ca.key" "$KEY_SIZE"

    # Generate CA certificate
    openssl req -new -x509 -days "$DAYS" -key "$CERTS_DIR/ca.key" -out "$CERTS_DIR/ca.crt" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=LocalCA"

    echo "CA certificate generated successfully!"
else
    echo "Using existing CA certificate..."
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

    echo "Generating server certificate for domains: ${domains[*]}"

    # Generate server private key
    openssl genrsa -out "$CERTS_DIR/${cert_name}.key" "$KEY_SIZE"

    # Create a config file for SAN (Subject Alternative Names)
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
    local i=1
    for domain in "${domains[@]}"; do
        echo "DNS.${i} = $domain" >> "$config_file"
        ((i++))
    done

    # Generate server certificate signing request with SAN
    openssl req -new -key "$CERTS_DIR/${cert_name}.key" -out "$CERTS_DIR/${cert_name}.csr" -config "$config_file"

    # Generate server certificate signed by CA with SAN extensions
    openssl x509 -req -days "$DAYS" -in "$CERTS_DIR/${cert_name}.csr" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial -out "$CERTS_DIR/${cert_name}.crt" -extensions v3_req -extfile "$config_file"

    # Clean up temporary files
    rm "$CERTS_DIR/${cert_name}.csr" "$config_file"

    echo "Server certificate generated successfully!"
    echo "  Certificate: $CERTS_DIR/${cert_name}.crt"
    echo "  Private Key: $CERTS_DIR/${cert_name}.key"
    echo "  Domains: ${domains[*]}"
}

# Copy CA certificate to Caddy trusted path (will be mounted in Docker)
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
    echo "  Domains: ${DOMAINS[*]}"
    echo "  Valid for: $DAYS days"
    echo "  Key size: $KEY_SIZE bits"
    echo "  Output directory: $CERTS_DIR"
    echo ""
    echo "Test server certificate:"
    echo "  curl --cacert $CERTS_DIR/ca.crt https://${DOMAINS[0]}/"
    exit 0
fi

# Generate client private key
openssl genrsa -out "$CERTS_DIR/${CLIENT_NAME}.key" "$KEY_SIZE"

# Generate client certificate signing request
openssl req -new -key "$CERTS_DIR/${CLIENT_NAME}.key" -out "$CERTS_DIR/${CLIENT_NAME}.csr" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=$CLIENT_NAME"

# Generate client certificate signed by CA
openssl x509 -req -days "$DAYS" -in "$CERTS_DIR/${CLIENT_NAME}.csr" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial -out "$CERTS_DIR/${CLIENT_NAME}.crt"

# Generate client certificate in PKCS#12 format for browsers
openssl pkcs12 -export -out "$CERTS_DIR/${CLIENT_NAME}.p12" -inkey "$CERTS_DIR/${CLIENT_NAME}.key" -in "$CERTS_DIR/${CLIENT_NAME}.crt" -certfile "$CERTS_DIR/ca.crt" -password pass:changeme

# Clean up CSR file
rm "$CERTS_DIR/${CLIENT_NAME}.csr"

# Set appropriate permissions
chmod 600 "$CERTS_DIR"/*.key
chmod 644 "$CERTS_DIR"/*.crt "$CERTS_DIR"/*.p12

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
echo "  Client Name: $CLIENT_NAME"
echo "  Server Domains: ${DOMAINS[*]}"
echo "  Valid for: $DAYS days"
echo "  Key size: $KEY_SIZE bits"
echo "  Output directory: $CERTS_DIR"
echo ""
echo "Test with curl:"
echo "  curl --cacert $CERTS_DIR/ca.crt --cert $CERTS_DIR/${CLIENT_NAME}.crt --key $CERTS_DIR/${CLIENT_NAME}.key https://${DOMAINS[0]}/"
