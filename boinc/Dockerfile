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
    dpkg --print-architecture | grep -q "amd64" && apt-get install --no-install-recommends -y intel-opencl-icd && \
    rm -rf /var/lib/apt/lists/*

# Copy operator
COPY operator/*.py /opt/operator/

# Entrypoint & CMD
ENTRYPOINT [ "python3", "/opt/operator/main.py", "--options", "/data/options.json", "--data", "/data/boinc", "--config", "/config" ]
