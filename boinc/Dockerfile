ARG BUILD_FROM="amd64/debian:12.8-slim"

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

# Install boinc client
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install --no-install-recommends -y boinc-client \
    python3-dict2xml \
    ocl-icd-libopencl1 \
    mesa-opencl-icd \
    libgl1 && \
    if [ "$BUILD_ARCH" = "amd64" ]; then apt-get install --no-install-recommends -y intel-opencl-icd; fi && \
    rm -rf /var/lib/apt/lists/*

# Copy operator
COPY operator/*.py /opt/operator/

# Entrypoint & CMD
ENTRYPOINT [ "python3", "/opt/operator/main.py", "--options", "/data/options.json", "--data", "/data/boinc", "--config", "/config" ]

# Build arugments
ARG BUILD_ARCH=amd64
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION
ARG BUILD_REPOSITORY

# Labels
LABEL \
    io.hass.name="Home Assistant Boinc Add-on for ${BUILD_ARCH}" \
    io.hass.description="Home Assistant Boinc Add-on for ${BUILD_ARCH}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.title="Home Assistant Boinc Add-on for ${BUILD_ARCH}" \
    org.opencontainers.image.description="Home Assistant Boinc Add-on for ${BUILD_ARCH}" \
    org.opencontainers.image.vendor="Home Assistant Boinc Add-ons" \
    org.opencontainers.image.authors="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.licenses="Apache2" \
    org.opencontainers.image.url="https://hectorespert.github.io/boinc-addons" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
