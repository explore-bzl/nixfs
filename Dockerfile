FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    fuse \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install fusepy using pip to ensure it's available for Python 3.10
RUN pip install fusepy

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

ADD https://hydra.nixos.org/build/254313966/download/1/nix /bin/nix
RUN chmod +x /bin/nix

COPY rootfs/bin/nixfs.py /bin/storefs

ENV PYTHONPATH=/usr/local/lib/python3.10/site-packages

ENTRYPOINT ["/bin/storefs"]
