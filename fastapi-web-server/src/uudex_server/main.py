import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from uudex_server.core import get_logger
from uudex_server.core.settings import Settings, get_settings

logger = get_logger("uudex_server.main")
logger.debug("Starting UUDEX Server")


def initialize_settings() -> Settings:
    try:
        settings = get_settings()
        return settings
    except ValueError as e:
        if "pytest" not in sys.modules:
            logger.error(str(e))
            sys.exit(1)
        raise


# Initialize settings
try:
    settings = initialize_settings()
    logger.info("Settings initialized successfully")
except Exception as e:
    if "pytest" not in sys.modules:
        logger.error(f"Failed to initialize settings: {e}")
        sys.exit(1)
    raise

from uudex_server.routes import add_routers

# Create FastAPI app, don't define docs url here, we are going to use our own endpoint.
app = FastAPI(
    title="UUDEX API",
    version="1.1.0",
    description="UUDEX Data Exchange API - Version 1.1",
    docs_url=None,
)

# Adds the endpoint routers to the FastAPI apphe FastAPI app
add_routers(app)
########################################################################################################################################################
# Middleware functions
# These are loaded in reverse order.  So the first one listed is the last# These are loaded in reverse order.  So the first one listed is the last
# one called.  As they are chained together, the first one called is thehe first one called is the
# last one listed. And will finish after all of the others have finished.d. And will finish after all of the others have finished.
########################################################################################################################################################


@app.middleware("http")
async def check_ssl_cert(request: Request, call_next):
    """
    This middleware method uses the request to determine whether or not a user
    is authorized.
    """
    logger.debug("Checking SSL Cert")

    # Check for Caddy's client certificate headers
    cert_subject = request.headers.get("X-Client-Cert-Subject")
    cert_issuer = request.headers.get("X-Client-Cert-Issuer")
    cert_serial = request.headers.get("X-Client-Cert-Serial")
    # Check if this is a public endpoint
    public_paths = ["/docs", "/openapi.json", "/health", "/status"]
    if any(request.url.path.startswith(path) for path in public_paths):
        logger.debug("Public endpoint accessed, skipping certificate check.")
        return await call_next(request)
    if not cert_subject:
        return JSONResponse(status_code=401, content="No certificate detected.")

    logger.debug(f"Certificate subject: {cert_subject}")
    logger.debug(f"Certificate issuer: {cert_issuer}")
    logger.debug(f"Certificate serial: {cert_serial}")

    # Extract CN from subject DN (format: CN=alice,O=Acme Corp,C=US)
    cn = None
    for part in cert_subject.split(","):
        if part.strip().startswith("CN="):
            cn = part.strip()[3:]  # Remove 'CN=' prefix
            break

    if not cn:
        return JSONResponse(status_code=401, content="No Common Name found in certificate.")

    logger.debug(f"Extracted CN: {cn}")

    # For now, let's skip the database check to test the basic functionality
    # Uncomment this section when you want to enable database validation
    """
    from uudex_server.repos import EndpointRepository
    from uudex_server.services.database_service import get_db_session

    async with get_db_session() as session:
        er = EndpointRepository(session)
        endpoint = await er.select_endpoint_by_certificate_dn(certificate_dn=cn)

        if not endpoint:
            return JSONResponse(status_code=401, content="Unauthorized certificate detected.")

        if endpoint.endpoint_id is None:
            return JSONResponse(status_code=401, content="Endpoint ID is missing in the certificate.")

        participant = await er.select_participant_by_endpoint_id(endpoint_id=endpoint.endpoint_id)

        request.state.endpoint = endpoint
        request.state.participant = participant
    """

    # Store certificate info in request state for use in endpoints
    request.state.cert_subject = cert_subject
    request.state.cert_issuer = cert_issuer
    request.state.cert_serial = cert_serial
    request.state.cert_cn = cn

    return await call_next(request)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.debug(f"Process time: {process_time}")
    return response


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    from fastapi.openapi.docs import get_swagger_ui_html

    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Documentation")


@app.get("/openapi.json", include_in_schema=False)
async def openapi():
    return app.openapi()


@app.get("/")
async def root(request: Request):
    # Get certificate info from request state
    cert_info = {
        "subject": getattr(request.state, "cert_subject", "Not available"),
        "issuer": getattr(request.state, "cert_issuer", "Not available"),
        "serial": getattr(request.state, "cert_serial", "Not available"),
        "cn": getattr(request.state, "cert_cn", "Not available"),
    }

    return {
        "message": "Hello World",
        "certificate_info": cert_info,
        "headers": dict(request.headers),
    }
