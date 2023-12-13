# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

# Install boinc client
RUN apt-get update && \
    apt-get install --no-install-recommends -y boinc-client ocl-icd-libopencl1 mesa-opencl-icd && \
    bash -c 'arch=$(dpkg --print-architecture); if [ "$arch" = "amd64" ]; then apt-get install --no-install-recommends -y intel-opencl-icd; fi'  && \
    rm -rf /var/lib/apt/lists/*

# Copy root filesystem
COPY rootfs /
