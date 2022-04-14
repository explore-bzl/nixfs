FROM ubuntu:latest
RUN apt-get update && apt-get install -y python3 python3-fusepy fuse ca-certificates
COPY rootfs/bin/nixfs.py /bin/nixfs
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
RUN python3 -c "from urllib.request import urlretrieve; urlretrieve('https://hydra.nixos.org/build/170454219/download/1/nix', '/bin/nix')" && chmod +x /bin/nix
RUN mkdir /nix && mkdir /not_nix && mkdir -p /true_nix/store && ln -s /true_nix /true_nix/nix
ENV PYTHONPATH=/lib/python3.9/site-packages
CMD ["/bin/nixfs", "/true_nix", "/nix"]
