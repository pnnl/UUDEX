# Build and runtime both use the pinned tag; the digest makes a rebuild reproducible.
ARG PYTHON_IMAGE=python:3.13.15-alpine3.24@sha256:79e7a9b9ff1cbceff819f856fb374477792a5967759d94df266de7b7b4120e6f

FROM ${PYTHON_IMAGE} AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN /opt/venv/bin/pip install .

FROM ${PYTHON_IMAGE}
# UUDEX_SECRETS_DIR is a directory path, not a secret value.
# hadolint ignore=DL3064
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UUDEX_SECRETS_DIR=/run/secrets
RUN addgroup -S -g 10001 uudex \
    && adduser -S -u 10001 -G uudex -H -s /sbin/nologin uudex
COPY --from=builder /opt/venv /opt/venv
USER 10001:10001
# Never publish port 8000: the app trusts the client-certificate header, so only the
# verifying proxy may reach it, over an internal network (see the README warning).
EXPOSE 8000
# Secrets are files under /run/secrets (UUDEX_SECRETS_DIR); nothing secret is passed here.
# They must be readable by uid 10001 (owner 10001, mode 0400), or startup fails.
CMD ["uvicorn", "uudex_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
