#!/bin/bash

# Script to generate certificates from existing PostgreSQL endpoint data
# This script reads the endpoint table and creates certificates for each certificate_dn

# Default values
DEFAULT_ORG="UUDEX"
DEFAULT_COUNTRY="US"
DEFAULT_STATE="State"
DEFAULT_CITY="City"
DEFAULT_DAYS="365"
DEFAULT_KEY_SIZE="4096"
DEFAULT_CERTS_DIR="certs"

# Certificate output directory (can be overridden by UUDEX_CERTS environment variable)
CERTS_DIR="${UUDEX_CERTS:-$DEFAULT_CERTS_DIR}"

# Database connection settings
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-uudex}"
DB_USER="${DB_USER:-uudex_user}"
DB_PASSWORD="${DB_PASSWORD:-uudex}"

# Function to display help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Generate client certificates from existing PostgreSQL endpoint data"
    echo ""
    echo "This script connects to the UUDEX PostgreSQL database, reads the endpoint"
    echo "table, and generates certificates based on the certificate_dn field."
    echo ""
    echo "Options:"
    echo "  -H, --host HOST     Database host (default: $DB_HOST)"
    echo "  -P, --port PORT     Database port (default: $DB_PORT)"
    echo "  -d, --database DB   Database name (default: $DB_NAME)"
    echo "  -u, --user USER     Database user (default: $DB_USER)"
    echo "  -p, --password PASS Database password (default: $DB_PASSWORD)"
    echo "  -c, --country CODE  Country code (default: $DEFAULT_COUNTRY)"
    echo "  -s, --state STATE   State or province (default: $DEFAULT_STATE)"
    echo "  -l, --city CITY     City or locality (default: $DEFAULT_CITY)"
    echo "  --days DAYS         Certificate validity in days (default: $DEFAULT_DAYS)"
    echo "  --key-size SIZE     RSA key size in bits (default: $DEFAULT_KEY_SIZE)"
    echo "  -o, --output-dir DIR Output directory for certificates (overrides UUDEX_CERTS)"
    echo "  --dry-run           Show what would be done without generating certificates"
    echo "  --force             Regenerate certificates even if they already exist"
    echo "  --active-only       Only generate certificates for active endpoints (active_sw='Y')"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  UUDEX_CERTS         Override certificate output directory (default: $DEFAULT_CERTS_DIR)"
    echo "  DB_HOST             Database host"
    echo "  DB_PORT             Database port"
    echo "  DB_NAME             Database name"
    echo "  DB_USER             Database user"
    echo "  DB_PASSWORD         Database password"
    echo ""
    echo "Examples:"
    echo "  $0                                      # Generate all certificates with defaults"
    echo "  $0 --dry-run                           # Show what would be done"
    echo "  $0 --active-only                       # Only active endpoints"
    echo "  $0 --force                             # Regenerate existing certificates"
    echo "  $0 -H postgres.example.com -u admin    # Use different database connection"
    echo "  $0 --output-dir /custom/certs          # Custom output directory"
    echo ""
}

# Initialize variables
ORG="$DEFAULT_ORG"
COUNTRY="$DEFAULT_COUNTRY"
STATE="$DEFAULT_STATE"
CITY="$DEFAULT_CITY"
DAYS="$DEFAULT_DAYS"
KEY_SIZE="$DEFAULT_KEY_SIZE"
DRY_RUN=false
FORCE=false
ACTIVE_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -H|--host)
            DB_HOST="$2"
            shift 2
            ;;
        -P|--port)
            DB_PORT="$2"
            shift 2
            ;;
        -d|--database)
            DB_NAME="$2"
            shift 2
            ;;
        -u|--user)
            DB_USER="$2"
            shift 2
            ;;
        -p|--password)
            DB_PASSWORD="$2"
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
        --days)
            DAYS="$2"
            shift 2
            ;;
        --key-size)
            KEY_SIZE="$2"
            shift 2
            ;;
        -o|--output-dir)
            CERTS_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --active-only)
            ACTIVE_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check for required tools
check_dependencies() {
    local missing=()

    if ! command -v psql &> /dev/null; then
        missing+=("psql")
    fi

    if ! command -v openssl &> /dev/null; then
        missing+=("openssl")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo "Error: Missing required dependencies: ${missing[*]}"
        echo ""
        echo "Please install the missing tools:"
        echo "  Ubuntu/Debian: sudo apt-get install postgresql-client openssl"
        echo "  macOS: brew install postgresql openssl"
        echo "  RHEL/CentOS: sudo yum install postgresql openssl"
        exit 1
    fi
}

# Function to extract CN from certificate DN
extract_cn_from_dn() {
    local dn="$1"

    # Handle various DN formats like "CN=alice" or "/CN=alice/O=Org" or "CN=alice,O=Org"
    if [[ "$dn" =~ CN=([^,/]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        # If no CN found, use the whole DN (but clean it up)
        echo "$dn" | sed 's/CN=//g' | sed 's/[,/]/_/g' | tr -d ' '
    fi
}

# Function to sanitize filename
sanitize_filename() {
    local name="$1"
    # Replace problematic characters with underscores
    echo "$name" | sed 's/[^a-zA-Z0-9._-]/_/g'
}

# Function to test database connection
test_db_connection() {
    echo "Testing database connection..."

    if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &>/dev/null; then
        echo "Error: Cannot connect to database"
        echo "  Host: $DB_HOST"
        echo "  Port: $DB_PORT"
        echo "  Database: $DB_NAME"
        echo "  User: $DB_USER"
        echo ""
        echo "Please check your database connection settings and ensure the PostgreSQL server is running."
        echo "You can also set environment variables: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD"
        exit 1
    fi

    echo "Database connection successful!"
}

# Function to fetch endpoints from database
fetch_endpoints() {
    local where_clause=""
    if [ "$ACTIVE_ONLY" = true ]; then
        where_clause="WHERE active_sw = 'Y'"
    fi

    echo "Fetching endpoints from database..."

    # First check if endpoint table exists
    local table_exists
    table_exists=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'endpoint'
        );" 2>/dev/null)

    if [ "$table_exists" != "t" ]; then
        echo "Warning: 'endpoint' table does not exist in the database."
        echo "This usually means the database schema hasn't been fully initialized yet."
        echo ""
        echo "To create the endpoint table, you may need to:"
        echo "1. Run database migrations"
        echo "2. Uncomment the endpoint table creation in the SQL schema files"
        echo "3. Manually create the table with the following structure:"
        echo ""
        echo "CREATE TABLE endpoint ("
        echo "    endpoint_id           serial          NOT NULL,"
        echo "    endpoint_uuid         char(36)        NOT NULL,"
        echo "    endpoint_user_name    varchar(30)     NOT NULL,"
        echo "    certificate_dn        varchar(255)    NOT NULL,"
        echo "    description           varchar(255),"
        echo "    active_sw             char(1)         NOT NULL CHECK (active_sw IN ('Y', 'N')),"
        echo "    uudex_administrator_sw char(1)        NOT NULL CHECK (uudex_administrator_sw IN ('Y', 'N')),"
        echo "    participant_administrator_sw char(1) NOT NULL CHECK (participant_administrator_sw IN ('Y', 'N')),"
        echo "    create_datetime       timestamp       NOT NULL,"
        echo "    participant_id        int4            NOT NULL,"
        echo "    CONSTRAINT pk_endpoint PRIMARY KEY (endpoint_id)"
        echo ");"
        echo ""
        return 1
    fi

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F$'\t' -c "
        SELECT
            endpoint_id,
            endpoint_user_name,
            certificate_dn,
            description,
            active_sw,
            uudex_administrator_sw,
            participant_administrator_sw
        FROM endpoint
        $where_clause
        ORDER BY endpoint_id;" 2>/dev/null
}

# Function to generate CA if it doesn't exist
generate_ca_if_needed() {
    if [ ! -f "$CERTS_DIR/ca.key" ] || [ ! -f "$CERTS_DIR/ca.crt" ]; then
        echo "Generating new CA certificate..."

        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY RUN] Would generate CA certificate in $CERTS_DIR/"
            return
        fi

        # Create certs directory
        mkdir -p "$CERTS_DIR"

        # Generate CA private key
        openssl genrsa -out "$CERTS_DIR/ca.key" "$KEY_SIZE"

        # Generate CA certificate
        openssl req -new -x509 -days "$DAYS" -key "$CERTS_DIR/ca.key" -out "$CERTS_DIR/ca.crt" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=UUDEX-CA"

        # Copy CA certificate to trusted path
        cp "$CERTS_DIR/ca.crt" "$CERTS_DIR/ca-trusted.crt"

        echo "CA certificate generated successfully!"
    else
        echo "Using existing CA certificate..."
    fi
}

# Function to generate client certificate
generate_client_certificate() {
    local endpoint_id="$1"
    local endpoint_user_name="$2"
    local certificate_dn="$3"
    local description="$4"
    local active_sw="$5"
    local uudex_admin_sw="$6"
    local participant_admin_sw="$7"

    # Extract client name from DN
    local client_name
    client_name=$(extract_cn_from_dn "$certificate_dn")

    # Sanitize filename
    local safe_filename
    safe_filename=$(sanitize_filename "$client_name")

    local cert_file="$CERTS_DIR/${safe_filename}.crt"
    local key_file="$CERTS_DIR/${safe_filename}.key"
    local p12_file="$CERTS_DIR/${safe_filename}.p12"

    # Check if certificate already exists
    if [ "$FORCE" != true ] && [ -f "$cert_file" ] && [ -f "$key_file" ]; then
        echo "  Certificate already exists for $client_name (use --force to regenerate)"
        return
    fi

    echo "  Generating certificate for: $client_name"
    echo "    Endpoint ID: $endpoint_id"
    echo "    User Name: $endpoint_user_name"
    echo "    DN: $certificate_dn"
    echo "    Description: $description"
    echo "    Active: $active_sw"
    echo "    UUDEX Admin: $uudex_admin_sw"
    echo "    Participant Admin: $participant_admin_sw"

    if [ "$DRY_RUN" = true ]; then
        echo "    [DRY RUN] Would generate:"
        echo "      Certificate: $cert_file"
        echo "      Private Key: $key_file"
        echo "      PKCS#12: $p12_file"
        echo ""
        return
    fi

    # Generate client private key
    openssl genrsa -out "$key_file" "$KEY_SIZE"

    # Generate client certificate signing request
    openssl req -new -key "$key_file" -out "$CERTS_DIR/${safe_filename}.csr" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=$client_name"

    # Generate client certificate signed by CA
    openssl x509 -req -days "$DAYS" -in "$CERTS_DIR/${safe_filename}.csr" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial -out "$cert_file"

    # Generate client certificate in PKCS#12 format for browsers
    openssl pkcs12 -export -out "$p12_file" -inkey "$key_file" -in "$cert_file" -certfile "$CERTS_DIR/ca.crt" -password pass:changeme

    # Clean up CSR file
    rm "$CERTS_DIR/${safe_filename}.csr"

    # Set appropriate permissions
    chmod 600 "$key_file"
    chmod 644 "$cert_file" "$p12_file"

    echo "    Certificate generated successfully!"
    echo "      Certificate: $cert_file"
    echo "      Private Key: $key_file"
    echo "      PKCS#12: $p12_file (password: changeme)"
    echo ""
}

# Main execution
main() {
    echo "UUDEX Certificate Generator from PostgreSQL Data"
    echo "================================================"
    echo ""

    # Check dependencies
    check_dependencies

    # Test database connection
    test_db_connection

    # Generate CA if needed
    generate_ca_if_needed

    # Fetch endpoints and generate certificates
    echo ""
    echo "Fetching endpoints and generating certificates..."
    echo ""

    local count=0
    local generated=0
    local skipped=0

    # Read endpoints from database
    local endpoints_data
    endpoints_data=$(fetch_endpoints)
    local fetch_status=$?

    if [ $fetch_status -ne 0 ]; then
        echo "Cannot proceed: endpoint table does not exist."
        exit 1
    fi

    if [ -z "$endpoints_data" ]; then
        echo "No endpoints found in the database."
        if [ "$ACTIVE_ONLY" = true ]; then
            echo "Note: --active-only flag was used. Try without it to include inactive endpoints."
        fi
        echo ""
        echo "To test this script, you can add sample data to the endpoint table:"
        echo ""
        echo "INSERT INTO endpoint (endpoint_uuid, endpoint_user_name, certificate_dn, description, active_sw, uudex_administrator_sw, participant_administrator_sw, create_datetime, participant_id) VALUES"
        echo "('$(uuidgen)', 'alice', 'CN=alice', 'Alice Test User', 'Y', 'N', 'N', CURRENT_TIMESTAMP, 1),"
        echo "('$(uuidgen)', 'bob', 'CN=bob,O=UUDEX', 'Bob Admin User', 'Y', 'Y', 'Y', CURRENT_TIMESTAMP, 1);"
        echo ""
        return
    fi

    while IFS=$'\t' read -r endpoint_id endpoint_user_name certificate_dn description active_sw uudex_admin_sw participant_admin_sw; do
        # Skip empty lines
        [ -z "$endpoint_id" ] && continue

        count=$((count + 1))

        echo "Processing endpoint $count:"

        if [ "$FORCE" != true ] && [ -f "$CERTS_DIR/$(sanitize_filename "$(extract_cn_from_dn "$certificate_dn")").crt" ]; then
            echo "  Certificate already exists for $(extract_cn_from_dn "$certificate_dn") (skipped)"
            skipped=$((skipped + 1))
        else
            generate_client_certificate "$endpoint_id" "$endpoint_user_name" "$certificate_dn" "$description" "$active_sw" "$uudex_admin_sw" "$participant_admin_sw"
            generated=$((generated + 1))
        fi

    done <<< "$endpoints_data"

    # Summary
    echo ""
    echo "Certificate generation completed!"
    echo "================================"
    echo "Total endpoints processed: $count"
    echo "Certificates generated: $generated"
    echo "Certificates skipped: $skipped"
    echo ""
    echo "Certificate details:"
    echo "  Country: $COUNTRY"
    echo "  State: $STATE"
    echo "  City: $CITY"
    echo "  Organization: $ORG"
    echo "  Valid for: $DAYS days"
    echo "  Key size: $KEY_SIZE bits"
    echo "  Output directory: $CERTS_DIR"
    echo ""

    if [ "$DRY_RUN" != true ] && [ "$generated" -gt 0 ]; then
        echo "Generated certificates can be found in: $CERTS_DIR"
        echo ""
        echo "Test with curl (replace CLIENT_NAME with actual certificate name):"
        echo "  curl --cacert $CERTS_DIR/ca.crt --cert $CERTS_DIR/CLIENT_NAME.crt --key $CERTS_DIR/CLIENT_NAME.key https://localhost:8443/"
    fi

    if [ "$count" -eq 0 ]; then
        echo "No endpoints found in the database."
        if [ "$ACTIVE_ONLY" = true ]; then
            echo "Note: --active-only flag was used. Try without it to include inactive endpoints."
        fi
    fi
}

# Run main function
main "$@"
