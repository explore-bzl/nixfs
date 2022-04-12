# execfs based remote worker registration
aka. naive way of solving: https://github.com/NixOS/nix/issues/523 using execfs.
This will eventually become a part of "distributed nix example".

## Quickstart
1. Build a "lister" container image:
```
# host
docker build . --name localhost/lister
```
2. Create a workdir:
```
# host
mkdir workdir
```
3. Start a "lister" container:
```
# host
docker run --cap-add CAP_SYS_ADMIN --device /dev/fuse -v $(pwd)/workdir:/workdir:shared -v /var/run/docker.sock:/var/run/docker.sock:ro --name nix_lister --rm -d localhost/lister:latest
```
4. Start dummy "worker" containers:
```
# host
seq 0 2 | while read line; do docker run --rm -d --name "nix_worker_${line}" nixery.dev/shell sleep infinity; done
```
5. Start a dummy "scheduler" container:
```
# host
docker run -v $(pwd)/workdir/machines:/etc/nix/machines -v $(pwd)/workdir/ssh_config:/root/.ssh/config --rm --name nix_scheduler -it nixery.dev/shell bash
```
6. In a "scheduler" container, observe how contents of `/etc/nix/machines` and `/root/.ssh/config` reflect currently active `nix_worker` instances:
```
# nix_scheduler
cat /etc/nix/machines 
nix_worker_2 x86_64-linux /etc/nix/worker_rsa 4
nix_worker_1 x86_64-linux /etc/nix/worker_rsa 4
nix_worker_0 x86_64-linux /etc/nix/worker_rsa 4

cat /root/.ssh/config 
Host 172.17.0.5
        HostName nix_worker_2
        Port 4022
        IdentityFile /root/.ssh/id_rsa
Host 172.17.0.4
        HostName nix_worker_1
        Port 4022
        IdentityFile /root/.ssh/id_rsa
Host 172.17.0.3
        HostName nix_worker_0
        Port 4022
        IdentityFile /root/.ssh/id_rsa
```
```
# host
docker kill nix_worker_1
```
```
# nix_scheduler
cat /etc/nix/machines 
nix_worker_2 x86_64-linux /etc/nix/worker_rsa 4
nix_worker_0 x86_64-linux /etc/nix/worker_rsa 4

cat /root/.ssh/config 
Host 172.17.0.5
        HostName nix_worker_2
        Port 4022
        IdentityFile /root/.ssh/id_rsa
Host 172.17.0.3
        HostName nix_worker_0
        Port 4022
        IdentityFile /root/.ssh/id_rsa
```
7. Cleanup
```
docker kill nix_worker_0 nix_worker_2 nix_lister
```
