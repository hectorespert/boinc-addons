ARG BUILD_FROM="amd64/debian:13.5-slim"

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

# Create installation script to handle architecture detection
RUN cat > /tmp/install-ttyd.sh << 'EOF'
#!/bin/bash
set -ex

# Update and install base dependencies
apt-get update
apt-get install --no-install-recommends -y \
    boinctui \
    ca-certificates \
    curl
rm -rf /var/lib/apt/lists/*

# Detect architecture using dpkg
CONTAINER_ARCH=$(dpkg --print-architecture)
echo "Container architecture detected as: $CONTAINER_ARCH"

# Map to ttyd release architecture name
if [ "$CONTAINER_ARCH" = "arm64" ]; then
    TTYD_ARCH="aarch64"
else
    TTYD_ARCH="x86_64"
fi

echo "Will download ttyd for architecture: $TTYD_ARCH"

# Download ttyd
TTYD_VERSION="1.7.7"
curl -fL -o /usr/local/bin/ttyd \
    "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${TTYD_ARCH}"
    
if [ ! -f /usr/local/bin/ttyd ]; then
    echo "ERROR: Failed to download ttyd binary"
    exit 1
fi

chmod +x /usr/local/bin/ttyd

# Clean up
apt-get remove -y curl
apt-get autoremove -y
apt-get clean
rm -rf /var/lib/apt/lists/*

echo "ttyd installation completed successfully for $TTYD_ARCH"
EOF

chmod +x /tmp/install-ttyd.sh
/tmp/install-ttyd.sh
rm /tmp/install-ttyd.sh

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
    io.hass.name="Home Assistant boinctui Add-on" \
    io.hass.description="Home Assistant boinctui Add-on" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.title="Home Assistant boinctui Add-on" \
    org.opencontainers.image.description="Home Assistant boinctui Add-on" \
    org.opencontainers.image.vendor="Hector Espert" \
    org.opencontainers.image.authors="Hector Espert <hectorespertpardo@gmail.com>" \
    org.opencontainers.image.licenses="Apache 2.0" \
    org.opencontainers.image.url="https://github.com/hectorespert/boinc-addons" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
