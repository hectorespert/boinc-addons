# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

# Install boinc client
RUN apt-get update && apt-get install -y boinc-client && rm -rf /var/lib/apt/lists/*

# Copy root filesystem
COPY rootfs /
