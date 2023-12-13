# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

# Install boinc client
RUN apt-get update && \
    apt-get install --no-install-recommends -y boinc-client ocl-icd-libopencl1 intel-opencl-icd mesa-opencl-icd && \
    rm -rf /var/lib/apt/lists/*

# Copy root filesystem
COPY rootfs /
