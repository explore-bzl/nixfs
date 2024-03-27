FROM ubuntu:latest
RUN apt-get update && \
    apt-get install -y python3 python3-fusepy python3-cachetools fuse ca-certificates && \
    rm -rf /var/lib/apt/lists/*
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
RUN python3 -c "from urllib.request import urlretrieve; urlretrieve('https://hydra.nixos.org/build/254313966/download/1/nix', '/bin/nix')" && \
    chmod +x /bin/nix
ENV PYTHONPATH=/usr/lib/python3.10/site-packages
COPY rootfs/bin/nixfs.py /bin/nixfs
CMD ["/bin/nixfs"]
