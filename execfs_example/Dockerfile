FROM nixery.dev/shell/python3packages.fusepy/python3/fuse/curl/jq AS builder
FROM scratch
COPY --from=builder / /
COPY rootfs/ /
ENV PYTHONPATH=/lib/python3.9/site-packages
CMD ["/bin/execfs", "/workdir"]

