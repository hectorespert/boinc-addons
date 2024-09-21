# Development


## Build locally (AMD 64 platform)
```bash
docker build --progress=plain -t hectorespert/amd64-addon-boinc .
```

## Run locally
```bash
docker run --rm -v boinc:/data hectorespert/amd64-addon-boinc
```