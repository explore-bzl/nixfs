{ pkgs ? import <nixpkgs> {} }:
let
  nixConf = pkgs.writeText "nix.conf" ''
    substituters = file:///src/.nix-cache https://cache.nixos.org/
    trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= 
    sandbox = false # Cannot use sandbox inside an unprivileged container
    '';

  entryPoint = ''
    #!${pkgs.stdenv.shell}
    mkdir -p /var/run/nix 
    mkdir -p /nix/var/nix
    ln -s /var/run/nix /nix/var/nix/daemon-socket
    (socat -d -d -d -lf socat.log UNIX-LISTEN:/var/run/nix/socket,reuseaddr,fork TCP-CONNECT:127.0.0.1:6666) &
    /bin/bash "$@"
    '';

in pkgs.dockerTools.buildImage {
  name = "localhost/client";
  tag = "latest";
  created = "now";

  contents = with pkgs; [
    iproute2
    coreutils
    bashInteractive
    cacert
    curl
    nix
    socat
    telnet
    git
  ];

  runAsRoot = ''
    #!${pkgs.stdenv.shell}
    ${pkgs.dockerTools.shadowSetup}
    mkdir -p /etc/nix /tmp /var/tmp /usr/bin
    chmod a=rwx,o+t /tmp /var/tmp
    cp ${nixConf} /etc/nix/nix.conf
    ln -s /bin/env /usr/bin/env
    cat <<'EOF' > /entry-point.sh
    ${entryPoint}
    EOF
    chmod +x /entry-point.sh 
  '';

  config = {
    WorkingDir = "/src";
    Cmd = [ "/entry-point.sh" ];
    Env = [
      "NIX_REMOTE=daemon"
      "NIX_PATH=nixpkgs=https://github.com/NixOS/nixpkgs/archive/30d3d79b7d3607d56546dd2a6b49e156ba0ec634.tar.gz"
      "PATH=/bin"
      "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
    ];
  };
}
