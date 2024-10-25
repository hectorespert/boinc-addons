# Development



## Build locally (AMD 64 platform)
```bash
docker build --progress=plain -t hectorespert/amd64-addon-boinc .
```

## Run locally
```bash
docker run -it --uts=host --pid=host --rm -v boinc:/data -v $(pwd)/operator/options.json:/data/options.json:ro hectorespert/amd64-addon-boinc
```
