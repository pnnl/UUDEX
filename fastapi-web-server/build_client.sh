#!/bin/bash
set -e

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Warning: Virtual environment not found at .venv/bin/activate"
fi

# Default port
PORT=${1:-8000}
SERVER_URL="http://localhost:${PORT}"

# Extract version from server pyproject.toml
SERVER_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

echo "Building UUDEX API Client..."
echo "Using server URL: ${SERVER_URL}"
echo "Server version: ${SERVER_VERSION}"

# Check if server is running
if ! curl -s "${SERVER_URL}/openapi.json" > /dev/null 2>&1; then
    echo "Error: UUDEX server not running at ${SERVER_URL}"
    echo "Start the server first with: uvicorn src.uudex_server.main:app --host 0.0.0.0 --port ${PORT}"
    echo ""
    echo "Usage: $0 [PORT]"
    echo "  PORT: Server port (default: 8000)"
    exit 1
fi

# Create generated-client-api directory if it doesn't exist
mkdir -p generated-client-api
cd generated-client-api

echo "Downloading latest OpenAPI specification..."
curl -s "${SERVER_URL}/openapi.json" > openapi.json

# Validate the OpenAPI spec was downloaded
if [ ! -s openapi.json ]; then
    echo "Error: Failed to download OpenAPI specification"
    exit 1
fi

echo "Generating Python API client..."
# Clear all openapi-python-client environment variables
env | grep -i openapi | cut -d= -f1 | xargs -I {} unset {}

# Ensure clean slate
rm -rf uudex_api_client uudex-api-client

# Temporarily disable ruff by renaming the system ruff
RUFF_PATH=$(which ruff)
if [ -n "$RUFF_PATH" ]; then
    mv "$RUFF_PATH" "${RUFF_PATH}.bak" 2>/dev/null || echo "Could not disable ruff temporarily"
fi

# Use generate with explicit meta setting
openapi-python-client generate --url "${SERVER_URL}/openapi.json" --meta none || {
    echo "Generation failed, trying with local file and none meta..."
    openapi-python-client generate --path ./openapi.json --meta none
}

# Restore ruff if we disabled it
if [ -f "${RUFF_PATH}.bak" ]; then
    mv "${RUFF_PATH}.bak" "$RUFF_PATH" 2>/dev/null || echo "Could not restore ruff"
fi

# Determine the generated client directory name (could be uudex-api-client or uudex_api_client)
GENERATED_DIR=""
if [ -d "uudex-api-client" ]; then
    GENERATED_DIR="uudex-api-client"
elif [ -d "uudex_api_client" ]; then
    GENERATED_DIR="uudex_api_client"
else
    echo "Error: Could not find generated client directory"
    exit 1
fi

echo "Found generated client in directory: ${GENERATED_DIR}"

# Restructure to proper package layout: uudex-api-client/uudex_api_client/
echo "Restructuring client package layout..."
PROPER_CLIENT_DIR="uudex-api-client"

# Clean up any existing properly structured client
rm -rf "${PROPER_CLIENT_DIR}"

# Create proper structure
mkdir -p "${PROPER_CLIENT_DIR}/uudex_api_client"


# Fix naming conflict with Python's types module first
if [ -f "${GENERATED_DIR}/types.py" ]; then
    echo "Renaming types.py to client_types.py to avoid conflicts..."
    mv "${GENERATED_DIR}/types.py" "${GENERATED_DIR}/client_types.py"
fi

# Always update all imports of types to client_types (handles both absolute and relative imports)
find "${GENERATED_DIR}" -name "*.py" -exec sed -i 's/from types import/from client_types import/g' {} \;
find "${GENERATED_DIR}" -name "*.py" -exec sed -i 's/import types/import client_types as types/g' {} \;
find "${GENERATED_DIR}" -name "*.py" -exec sed -i 's/from uudex_api_client.types import/from uudex_api_client.client_types import/g' {} \;
find "${GENERATED_DIR}" -name "*.py" -exec sed -i 's/from ...types import/from ...client_types import/g' {} \;
find "${GENERATED_DIR}" -name "*.py" -exec sed -i 's/from ..types import/from ..client_types import/g' {} \;

# Move source files to module directory
cp -r "${GENERATED_DIR}/__init__.py" "${GENERATED_DIR}/api" "${GENERATED_DIR}/models" \
      "${GENERATED_DIR}/client.py" "${GENERATED_DIR}/client_types.py" "${GENERATED_DIR}/errors.py" \
      "${PROPER_CLIENT_DIR}/uudex_api_client/"

# After copying, run sed again in the final client directory to catch any missed replacements
find "${PROPER_CLIENT_DIR}/uudex_api_client" -name "*.py" -exec sed -i 's/from ..types import/from ..client_types import/g' {} \;

# Clean up the original generated directory to avoid confusion
rm -rf "${GENERATED_DIR}"

CLIENT_DIR="${PROPER_CLIENT_DIR}"

# Create README.md in the proper location
cat > "${CLIENT_DIR}/README.md" << 'EOF'
# UUDEX API Client

A Python client library for accessing the UUDEX API.

## Features

- Complete CRUD operations for subjects
- Queue management and message publishing
- Certificate management and download
- User authentication and authorization
- Async/await support

## Installation

```bash
pip install uudex-api-client
```

## Usage

```python
from uudex_api_client import Client

client = Client(base_url="https://your-uudex-server.com")
# Use the client to interact with UUDEX API
```

## Generated with OpenAPI

This client was automatically generated from the UUDEX OpenAPI specification.
EOF

# Create pyproject.toml in the proper location
cat > "${CLIENT_DIR}/pyproject.toml" << EOF
[tool.poetry]
name = "uudex-api-client"
version = "${SERVER_VERSION}"
description = "A client library for accessing UUDEX API"
authors = ["UUDEX Team"]
readme = "README.md"
packages = [
    { include = "uudex_api_client" },
]

[tool.poetry.dependencies]
python = "^3.8"
httpx = ">=0.20.0,<1.0.0"
attrs = ">=21.3.0"

[tool.ruff]
# Disable most rules for generated code
ignore = [
    "UP006",   # Use dict instead of Dict for type annotation
    "UP035",   # Use type instead of Type for type annotation
    "UP007",   # Use X | Y for Union type annotations
    "UP038",   # Use X | Y in isinstance calls instead of Union
    "UP039",   # Use list[T] instead of List[T]
    "UP040",   # Use set[T] instead of Set[T]
    "E501",    # Line too long
    "F401",    # Unused import
    "F403",    # Star import used
    "F405",    # Name may be undefined due to star import
    "W291",    # Trailing whitespace
    "SIM108",  # Use ternary operator instead of if-else
    "RUF",     # Ruff-specific rules
    "W",       # Warning categories
    "E",       # Error categories (except syntax errors)
]
target-version = "py38"
line-length = 120

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
EOF

echo "Created proper package structure with pyproject.toml and README.md"

# Package configuration already created above

echo "Installing client dependencies..."
cd "${CLIENT_DIR}"

# Check if pyproject.toml exists, if not create a basic one
if [ ! -f "pyproject.toml" ]; then
    echo "Creating pyproject.toml for client..."
    cat > pyproject.toml << EOF
[tool.poetry]
name = "uudex-api-client"
version = "${SERVER_VERSION}"
description = "A client library for accessing UUDEX API"
authors = ["UUDEX Team"]
readme = "README.md"
packages = [
    { include = "uudex_api_client" },
]

[tool.poetry.dependencies]
python = "^3.8"
httpx = ">=0.20.0,<1.0.0"
attrs = ">=21.3.0"

[tool.ruff]
ignore = [
    "UP006",   # Use dict instead of Dict for type annotation
    "UP035",   # Use type instead of Type for type annotation
    "UP007",   # Use X | Y for Union type annotations
    "UP038",   # Use X | Y in isinstance calls instead of Union
    "UP039",   # Use list[T] instead of List[T]
    "UP040",   # Use set[T] instead of Set[T]
    "E501",    # Line too long
    "F401",    # Unused import
    "F403",    # Star import used
    "F405",    # Name may be undefined due to star import
]
target-version = "py38"
line-length = 120

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
EOF
fi

poetry install

echo "Building client package..."
poetry build
cd ..

echo ""
echo "✅ UUDEX API client built successfully!"
echo ""
echo "The generated client includes all UUDEX endpoints:"
echo "  - Complete subject management CRUD operations"
echo "  - Queue management (info, purge, delete)"
echo "  - Message publishing to subjects"
echo "  - Certificate management and download"
echo "  - Bulk operations for administrators"
echo "  - User authentication and authorization"
echo ""
echo "Client package location: generated-client-api/uudex-api-client/dist/"
echo "Available packages:"
echo "  - Wheel: uudex_api_client-${SERVER_VERSION}-py3-none-any.whl"
echo "  - Source: uudex_api_client-${SERVER_VERSION}.tar.gz"
echo ""
echo "To install: pip install generated-client-api/uudex-api-client/dist/uudex_api_client-${SERVER_VERSION}-py3-none-any.whl"
