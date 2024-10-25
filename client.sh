#!/usr/bin/env bash
set -euo pipefail
set -x 

docker run -v $(pwd)/tmp:/nix -it harbor.apps.morrigna.rules-nix.build/explore-bzl/ash:5mfaxwh59bw9g7747j33v4psf2g604vl /nix/store/2idc2ipafc7dwpr7q4cq77y4k9z93x1k-cowsay-3.7.0/bin/cowsay "Hello NixCon24!"

set +x
