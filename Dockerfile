FROM nixery.dev/shell/python3packages.fusepy/python3/fuse/cacert AS builder
FROM scratch
COPY --from=builder / /
COPY rootfs/ /
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt
RUN python3 -c "from urllib.request import urlretrieve; urlretrieve('https://hydra.nixos.org/build/170454219/download/1/nix', '/bin/nix')" && chmod +x /bin/nix
ENV PYTHONPATH=/lib/python3.9/site-packages
CMD ["nixfs.py", "/fakestore", "/workdir"]
