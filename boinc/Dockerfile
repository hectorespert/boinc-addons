ARG BUILD_FROM="ghcr.io/home-assistant/amd64-base-debian:bookworm"

# Operator Builder
# hadolint ignore=DL3006
FROM $BUILD_FROM  AS builder

# Install pipx
RUN apt-get update && \
    apt-get install --no-install-recommends -y python3-dev pipx binutils && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash builder

USER builder

WORKDIR /home/builder

RUN pipx install pyinstaller

COPY operator operator

RUN /home/builder/.local/bin/pyinstaller --onefile --name operator operator/main.py

# Boinc Addon Image
# hadolint ignore=DL3006
FROM $BUILD_FROM

# Install boinc client
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install --no-install-recommends -y boinc-client ocl-icd-libopencl1 mesa-opencl-icd libgl1 && \
    bash -c 'arch=$(dpkg --print-architecture); if [ "$arch" = "amd64" ]; then apt-get install --no-install-recommends -y intel-opencl-icd; fi'  && \
    rm -rf /var/lib/apt/lists/*

# COpy operator from builder
COPY --from=builder /home/builder/dist/operator /opt/operator/bin/operator

# Copy root filesystem
COPY rootfs /
