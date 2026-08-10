ARG BUILD_FROM="debian:13.6-slim"

# hadolint ignore=DL3006
FROM $BUILD_FROM

# Environment variables
ENV DEBIAN_FRONTEND="noninteractive" \
    LANG="C.UTF-8" \
    TERM="xterm-256color" \
    PS1="$(whoami)@$(hostname):$(pwd)$ " \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    python3 \
    python3-flask \
    python3-waitress && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy server
COPY server/*.py /opt/boincui/
COPY server/templates/ /opt/boincui/templates/

# Entrypoint & CMD
ENTRYPOINT [ "python3", "/opt/boincui/main.py" ]

# Build arguments
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION
ARG BUILD_ARCH
ARG BUILD_REPOSITORY

# Labels
LABEL \
    io.hass.name="Home Assistant BOINC UI Add-on" \
    io.hass.description="Home Assistant BOINC UI Add-on" \
    io.hass.arch=${BUILD_ARCH} \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.title="Home Assistant BOINC UI Add-on" \
    org.opencontainers.image.description="Home Assistant BOINC UI Add-on" \
    org.opencontainers.image.vendor="Hector Espert" \
    org.opencontainers.image.authors="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.url="https://hectorespert.github.io/boinc-addons" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
