#!/usr/bin/env bash
set -euo pipefail
set -x

docker build . --tag localhost/nixfs:latest

mkdir -p $(pwd)/tmp

docker run --name nixfs --rm --cap-add SYS_ADMIN -v $(pwd)/rootfs/bin/nixfs.py:/bin/storefs --device /dev/fuse -v $(pwd)/tmp:/root/nix:shared localhost/nixfs:latest

set +x
