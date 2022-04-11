# Distributed nix build + lazy nix store example
## Quickstart
1. Build and import container images
```
# host
nix-build && docker load < result
nix-build client.nix && docker load < result
rm -rf result
```
2. Create shared store mountpoint
```
# host
mkdir workdir
```
3. Launch builder container:
```
# host
docker run --network=host --cap-add=CAP_SYS_ADMIN --device=/dev/fuse --volume=$(pwd)/workdir:/workdir:shared -it localhost/builder:latest 
```
4. Launch client container:
```
# host
docker run --network=host -v $(pwd)/workdir/store:/nix/store -it localhost/client:latest
```
5. Start observing local processes in `builder` container:
```
# builder
top
```
6. In `client` container, try accessing some store path, which will invoke lazy fetching:
```
# client
/nix/store/h1bq899a50xjsd4314xahyqpaaz8z02l-lsd-0.21.0/bin/lsd
```
7. In `client` container, try building something:
```
# client
nix-build -E '(import <nixpkgs> {}).busybox.override { enableStatic = true; }'
```
