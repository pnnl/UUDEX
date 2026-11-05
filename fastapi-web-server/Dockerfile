# Build and runtime both use the pinned tag; the digest makes a rebuild reproducible.
ARG PYTHON_IMAGE=python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26

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
RUN groupadd --system --gid 10001 uudex \
    && useradd --system --uid 10001 --gid uudex --no-create-home --shell /usr/sbin/nologin uudex
COPY --from=builder /opt/venv /opt/venv
USER 10001:10001
EXPOSE 8000
# Secrets are files under /run/secrets (UUDEX_SECRETS_DIR); nothing secret is passed here.
CMD ["uvicorn", "uudex_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
