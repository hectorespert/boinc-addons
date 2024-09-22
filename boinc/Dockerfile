ARG BUILD_FROM="ghcr.io/home-assistant/amd64-base-debian:bookworm"

# hadolint ignore=DL3006
FROM $BUILD_FROM

# Install boinc client
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install --no-install-recommends -y boinc-client ocl-icd-libopencl1 mesa-opencl-icd libgl1 && \
    bash -c 'arch=$(dpkg --print-architecture); if [ "$arch" = "amd64" ]; then apt-get install --no-install-recommends -y intel-opencl-icd; fi'  && \
    rm -rf /var/lib/apt/lists/*

# Copy operator
COPY operator/*.py /opt/operator/

# Copy root filesystem
COPY rootfs /
