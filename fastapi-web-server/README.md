# UUDEX-Server

This server implementation uses FastAPI as its basis for data access.

The example secrets, passwords and database role in this directory are for local development only. They are not for real deployment.

**Warning:** the server takes client identity from the `X-Client-Cert-*` headers. Run it only behind a proxy that verifies client certificates and overwrites those headers. Do not expose it directly.

See (DEVLIST.md) for features and status of project

## URLS for this site

- (<https://localhost/api/docs>) Swaggar UI - It validates that you have a correct tls certificate
before allowing you to see anything.  NOTE: The client must have the ca and certificate key in the
browser before going to this site.

## PostGresql Setup

See (database-layer/README.md) for instructions on setting up the database using docker.

## Generating the client

1. Make sure you have activated the server code.
2. cd to the 'generated-client-api' directory.
3. Execute 'openapi-python-client update --path openapi.json'

## Updating the openapi.json file

1. Open a browser to the Swagger UI (<https://localhost/api/docs>)
2. Click on </api/openapi.json> under the title of UUDEX API.
