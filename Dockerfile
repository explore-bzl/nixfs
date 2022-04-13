FROM ubuntu:latest
RUN apt-get update && apt-get install -y python3 python3-fusepy fuse ca-certificates strace
COPY rootfs/bin/nixfs.py /bin/nixfs
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
RUN python3 -c "from urllib.request import urlretrieve; urlretrieve('https://hydra.nixos.org/build/170454219/download/1/nix', '/bin/nix')" && chmod +x /bin/nix
RUN echo 'notnix:x:1001:65534::/tmp:/bin/bash' >> /etc/passwd && echo 'notnix:*:19087:0:99999:7:::' >> /etc/shadow
RUN mkdir /nix && mkdir -p /fakenix/store && ln -s /fakenix /fakenix/nix && chown -R notnix: /fakenix
ENV PYTHONPATH=/lib/python3.9/site-packages
CMD ["/bin/nixfs", "/fakenix", "/nix"]
