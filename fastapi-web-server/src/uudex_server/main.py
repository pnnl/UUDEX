import ipaddress
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from uudex_server.core import get_logger
from uudex_server.core.client_cert import (
    FORWARDED_CERT_HEADER,
    ClientCertError,
    parse_forwarded_cert,
)
from uudex_server.core.settings import Settings, get_settings
from uudex_server.services.database_service import init_db, shutdown_db

logger = get_logger("uudex_server.main")
logger.debug("Starting UUDEX Server")


def initialize_settings() -> Settings:
    try:
        return get_settings()
    except ValidationError as e:
        if "pytest" in sys.modules:
            raise
        # Names and error types only: the error input would echo secret values.
        problems = [f"{'.'.join(map(str, err['loc']))} ({err['type']})" for err in e.errors()]
        logger.error("Invalid settings: " + ", ".join(problems))
        sys.exit(1)
    except ValueError as e:
        if "pytest" not in sys.modules:
            logger.error(str(e))
            sys.exit(1)
        raise


def warn_if_no_trusted_proxies(hosts: Sequence[object]) -> None:
    if not hosts:
        logger.warning(
            "trusted_proxy_hosts is empty: no peer is trusted, so every non-public request "
            "will be refused. Set TRUSTED_PROXY_HOSTS to a JSON list of the verifying "
            "proxy's addresses."
        )


# Initialize settings
settings = initialize_settings()
logger.info("Settings initialized successfully")
warn_if_no_trusted_proxies(settings.trusted_proxy_hosts)

from uudex_server.routes import add_routers


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    try:
        await init_db()
        yield
    finally:
        await shutdown_db()


# Create FastAPI app, don't define docs url here, we are going to use our own endpoint.
app = FastAPI(
    title="UUDEX API",
    version="1.1.0",
    description="UUDEX Data Exchange API - Version 1.1",
    docs_url=None,
    lifespan=lifespan,
)

# Adds the endpoint routers to the FastAPI apphe FastAPI app
add_routers(app)
########################################################################################################################################################
# Middleware functions
# These are loaded in reverse order.  So the first one listed is the last# These are loaded in reverse order.  So the first one listed is the last
# one called.  As they are chained together, the first one called is thehe first one called is the
# last one listed. And will finish after all of the others have finished.d. And will finish after all of the others have finished.
########################################################################################################################################################


PUBLIC_PATHS = frozenset({"/docs", "/openapi.json"})
UNTRUSTED_PEER_BODY = "Request not from a trusted proxy."
INVALID_CERT_BODY = "Invalid certificate."
CERT_REFUSAL_BODIES = {
    "absent": "No certificate detected.",
    "empty": "No certificate detected.",
    "no_cn": "No Common Name found in certificate.",
}


def _is_trusted_peer(peer: str | None) -> bool:
    """True only for a peer listed in trusted_proxy_hosts; anything unparsable is refused."""
    if peer is None:
        return False
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    # A dual-stack socket reports an IPv4 peer as ::ffff:a.b.c.d.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address in settings.trusted_proxy_hosts


@app.middleware("http")
async def check_ssl_cert(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    This middleware method uses the request to determine whether or not a user
    is authorized.
    """
    logger.debug("Checking SSL Cert")

    # Exact matches: a prefix test would also expose /docsx and /statusx.
    if request.url.path in PUBLIC_PATHS:
        logger.debug("Public endpoint accessed, skipping certificate check.")
        return await call_next(request)

    # The forwarded certificate is believed only from a trusted proxy, and the peer is checked
    # before any of them is read, so an untrusted peer cannot make them reach the log or parser.
    peer = request.client.host if request.client else None
    if not _is_trusted_peer(peer):
        logger.warning(f"Refused request from untrusted peer {peer}")
        return JSONResponse(status_code=401, content=UNTRUSTED_PEER_BODY)

    # The proxy verified the chain; the app only reads the leaf it forwards and never re-verifies.
    headers = request.headers.getlist(FORWARDED_CERT_HEADER)
    try:
        if len(headers) > 1:
            raise ClientCertError("multiple_headers")
        cert = parse_forwarded_cert(headers[0] if headers else None)
    except ClientCertError as e:
        logger.warning(f"Refused client certificate: {e.reason}")
        return JSONResponse(status_code=401, content=CERT_REFUSAL_BODIES.get(e.reason, INVALID_CERT_BODY))

    cn = cert.cn
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
    request.state.cert_subject = cert.subject
    request.state.cert_issuer = cert.issuer
    request.state.cert_serial = cert.serial
    request.state.cert_cn = cn

    return await call_next(request)


@app.middleware("http")
async def add_process_time_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
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
