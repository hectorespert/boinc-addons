ARG BUILD_FROM="amd64/debian:13.1-slim"

# hadolint ignore=DL3006
FROM $BUILD_FROM

# Environment variables
ENV DEBIAN_FRONTEND="noninteractive" \
    LANG="C.UTF-8" \
    TERM="xterm-256color" \
    PS1="$(whoami)@$(hostname):$(pwd)$ " \
    TTYD_VERSION="1.7.7"

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Build arguments for architecture mapping
ARG BUILD_ARCH=amd64

# Install runtime dependencies and download ttyd
# hadolint ignore=DL3008,DL3003
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    boinctui \
    ca-certificates \
    curl && \
    rm -rf /var/lib/apt/lists/* && \
    # Map Home Assistant arch to ttyd release arch
    case "${BUILD_ARCH}" in \
        amd64) TTYD_ARCH="x86_64" ;; \
        aarch64) TTYD_ARCH="aarch64" ;; \
        armv7) TTYD_ARCH="armv7" ;; \
        armhf) TTYD_ARCH="arm" ;; \
        i386) TTYD_ARCH="i686" ;; \
        *) echo "Unsupported architecture: ${BUILD_ARCH}" && exit 1 ;; \
    esac && \
    # Download ttyd binary from GitHub releases
    curl -L -o /usr/local/bin/ttyd \
        "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${TTYD_ARCH}" && \
    chmod +x /usr/local/bin/ttyd && \
    # Clean up
    apt-get remove -y curl && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create user with home in /data/boinctui
RUN useradd -m -d /data/boinctui -s /bin/bash boinctui

# Copy and setup startup script
COPY run.sh /
RUN chmod a+x /run.sh

# Entrypoint & CMD
ENTRYPOINT [ "/run.sh" ]

# Build arguments
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION
ARG BUILD_REPOSITORY

# Labels
LABEL \
    io.hass.name="Home Assistant boinctui Add-on for ${BUILD_ARCH}" \
    io.hass.description="Home Assistant boinctui Add-on for ${BUILD_ARCH}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.title="Home Assistant boinctui Add-on for ${BUILD_ARCH}" \
    org.opencontainers.image.description="Home Assistant boinctui Add-on for ${BUILD_ARCH}" \
    org.opencontainers.image.vendor="Hector Espert" \
    org.opencontainers.image.authors="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.licenses="Apache 2.0" \
    org.opencontainers.image.url="https://github.com/hectorespert/boinc-addons" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
