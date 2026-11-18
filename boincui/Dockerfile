ARG BUILD_FROM="debian:13.7-slim"

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

# aioboinc comes from PyPI because Debian does not package it. It goes into a venv that also sees
# Debian's site-packages, so flask and waitress still come from apt and the system Python is left
# alone. pip is only needed for the install and is purged in the same layer.
COPY server/requirements.txt /tmp/requirements.txt
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    python3 \
    python3-flask \
    python3-pip \
    python3-waitress && \
    python3 -m venv --system-site-packages --without-pip /opt/boincui/venv && \
    python3 -m pip --python /opt/boincui/venv/bin/python3 install --no-cache-dir -r /tmp/requirements.txt && \
    apt-get purge -y --auto-remove python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/requirements.txt

# Copy server
COPY server/*.py /opt/boincui/
COPY server/templates/ /opt/boincui/templates/

# Entrypoint & CMD
ENTRYPOINT [ "/opt/boincui/venv/bin/python3", "/opt/boincui/main.py", "--options", "/data/options.json" ]

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
