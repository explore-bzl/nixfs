#!/usr/bin/env bash

docker build . --tag localhost/nixfs:latest
cat << EOF | docker build --tag localhost/empty:latest -
FROM scratch
ENV EMPTY=1
EOF

mkdir -p $(pwd)/tmp

docker run --name nixfs --rm --cap-add SYS_ADMIN -v $(pwd)/rootfs/bin/nixfs.py:/bin/storefs --device /dev/fuse -v $(pwd)/tmp:/root/nix:shared localhost/nixfs:latest &

sleep 5
docker run -v $(pwd)/tmp:/nix -it localhost/empty:latest /nix/store/2idc2ipafc7dwpr7q4cq77y4k9z93x1k-cowsay-3.7.0/bin/cowsay "Hello NixCon24!"

docker stop nixfs
