FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    fuse \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install fusepy using pip to ensure it's available for Python 3.10
RUN pip install fusepy urllib3

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY rootfs/bin/nixfs.py /bin/storefs

ENV PYTHONPATH=/usr/local/lib/python3.10/site-packages

ENTRYPOINT ["/bin/storefs"]
