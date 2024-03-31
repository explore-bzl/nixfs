{ pkgs ? import <nixpkgs> {} }:

pkgs.stdenv.mkDerivation {
  name = "self-extracting-script-builder";
  src = ./.;

  buildInputs = [
    pkgs.bash
    pkgs.python3Packages.nuitka
    pkgs.python3Packages.fusepy
    pkgs.python3Packages.ordered-set
    pkgs.fuse
    pkgs.patchelf
    pkgs.sharutils
    pkgs.file
  ];

  buildPhase = ''
    export LIBFUSE_SO_PATH=${pkgs.fuse}/lib/libfuse.so 
    export LD_LIBRARY_PATH=''$LD_LIBRARY_PATH:${pkgs.libxcrypt}/lib
    bash ./build.sh nixfs.py
  '';

  installPhase = ''
    mkdir -p $out/bin
    cp *.sh $out/bin/
  '';
}

