# nixfs - lazy /nix/store based on FUSE

## Quickstart
1. Build server image with:
```
docker build . --tag localhost/nixfs:latest
```

2. Run server image:
```
mkdir {fakestore,workdir}

docker run --cap-add SYS_ADMIN\
 -v $(pwd)/fakestore:/fakestore:shared\
 -v $(pwd)/workdir:/workdir:shared\
 --device /dev/fuse\
 -it localhost/nixfs:latest
```

3. In a second terminal window, build a dummy image containing mostly symlinks
```
docker build --tag localhost/devshell:light - <<EOF
FROM nixery.dev/shell/curl/python3packages.fusepy/python3/lsd AS build
FROM scratch AS cleaner
COPY --from=build / /
RUN rm -rf /nix
FROM scratch
COPY --from=cleaner / /
EOF
```

4. Run the dummy image and observe how server fetches paths from `cache.nixos.org` as you access files:
```
docker run -v $(pwd)/workdir/nix:/nix -it localhost/devshell:light sh # fetches bash
PYTHONPATH=/lib/python3.9/site-packages python3 # fetches python
import fuse
```
