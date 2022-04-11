{
  devUserUid ? 1000
, pkgs ? import <nixpkgs> {}
}:
let
  nixConf = pkgs.writeText "nix.conf" ''
    substituters = file:///src/.nix-cache https://cache.nixos.org/
    trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= 
    sandbox = false # Cannot use sandbox inside an unprivileged container
    '';

  suExec = pkgs.pkgsMusl.su-exec.overrideAttrs(o:{CFLAGS="--static";});
  toybox-static = pkgs.pkgsMusl.toybox.override { enableStatic=true; };

  # The entryPoint starts up a nix-daemon in the background and su-execs to the
  # build user. This is to enable builds in multi-user mode so we don't need to
  # run nix commands as root
  entryPoint = pkgs.writeScript "entry-point.sh" ''
    #!${pkgs.stdenv.shell}
    mkdir -p /nix/var/nix
    mkdir -p /var/run/nix && ln -s /var/run/nix /nix/var/nix/daemon-socket
    (nix-daemon > /dev/shm/nix-daemon.log 2>&1) &
    (socat -d -d -d -lf /dev/shm/ns-socat.log TCP-LISTEN:6666,reuseaddr,fork UNIX-CLIENT:/var/run/nix/socket) &
    (${./nixfs.py} /nix /workdir) &
    export NIX_REMOTE=daemon
    su-exec dev:dev /bin/bash "$@"
    '';

in pkgs.dockerTools.buildImage {
  name = "localhost/builder";
  tag = "latest";
  created = "now";

  contents = with pkgs; [
    toybox-static
    bashInteractive
    cacert
    curl
    nixUnstable
    suExec
    socat
    git
    fuse3
    fuse
    (python3.withPackages (ps: with ps; [ fusepy ]))
  ];

  runAsRoot = ''
    #!${pkgs.stdenv.shell}
    ${pkgs.dockerTools.shadowSetup}
    mkdir -p /etc/nix /tmp /var/tmp /usr/bin
    chmod a=rwx,o+t /tmp /var/tmp
    groupadd nixbld -g 30000
    for i in {1..10}; do
      useradd -c "Nix build user $i" \
        -d /var/empty -g nixbld -G nixbld -M -N -r -s "/bin/nologin" nixbld$i || true
    done
    useradd \
      -c "Dev user" \
      -d /src \
      -s "/bin/bash" \
      -u ${toString devUserUid} \
      -U \
      dev
    cp ${nixConf} /etc/nix/nix.conf
    ln -s /bin/env /usr/bin/env
    echo 'user_allow_other' > /etc/fuse.conf
  '';
  config = {
    Cmd = [ entryPoint ];
    WorkingDir = "/src";
    Env = [
      "PATH=/bin"
      "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
    ];
  };
}
