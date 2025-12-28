# Development

## Build Locally (AMD 64 Platform)

```bash
docker build --progress=plain -t hectorespert/amd64-addon-boinc .
```

## Run Locally

```bash
docker run -it --uts=host --pid=host --rm -v boinc:/data -v $(pwd)/operator/options.json:/data/options.json:ro hectorespert/amd64-addon-boinc
```

## Updating BOINC Client Checksums

The Dockerfile includes SHA256 checksum verification for the BOINC client `.deb` files to ensure supply chain security. When updating to a new BOINC version, you must update the checksums in the Dockerfile.

### How to obtain checksums for a new BOINC release:

1. Download the `.deb` files for each architecture from the [BOINC releases page](https://github.com/BOINC/boinc/releases)
2. Calculate the SHA256 checksum for each file:

```bash
# For amd64
curl -L "https://github.com/BOINC/boinc/releases/download/client_release%2F8.2%2F8.2.8/boinc-client_8.2.8-3429_amd64_trixie.deb" -o boinc-amd64.deb
sha256sum boinc-amd64.deb

# For arm64
curl -L "https://github.com/BOINC/boinc/releases/download/client_release%2F8.2%2F8.2.8/boinc-client_8.2.8-3429_arm64_trixie.deb" -o boinc-arm64.deb
sha256sum boinc-arm64.deb

# For armhf
curl -L "https://github.com/BOINC/boinc/releases/download/client_release%2F8.2%2F8.2.8/boinc-client_8.2.8-3429_armhf_trixie.deb" -o boinc-armhf.deb
sha256sum boinc-armhf.deb
```

3. Update the `EXPECTED_SHA256` values in the Dockerfile's case statement with the calculated checksums
4. Update the download URL if the version number has changed

### Security Note

The checksum verification ensures that the downloaded file has not been tampered with. If the checksum doesn't match, the Docker build will fail with an error, preventing potentially compromised packages from being installed.
