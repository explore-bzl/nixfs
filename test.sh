#!/usr/bin/env bash

docker build . --tag localhost/nixfs:latest
cat << EOF | docker build --tag localhost/empty:latest -
FROM scratch
ENV EMPTY=1
EOF

docker run --name nixfs --rm --cap-add SYS_ADMIN -v $(pwd)/rootfs/bin/nixfs.py:/bin/storefs --device /dev/fuse -v $(pwd)/tmp:/root/nix:shared localhost/nixfs:latest &

sleep 5
docker run -v $(pwd)/tmp:/nix -it empty /nix/store/rnxji3jf6fb0nx2v0svdqpj9ml53gyqh-hello-2.12.1/bin/hello

docker kill nixfs
