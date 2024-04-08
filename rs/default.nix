{localSystem ? builtins.currentSystem, ...} @ args: let
  external_sources = import ./nix/sources.nix;

  rustOverlaySource = external_sources."rust-overlay";
  rustOverlay = import "${rustOverlaySource}/default.nix";

  nixpkgs_import_args = {
    inherit localSystem;
    config = {};
    overlays = [rustOverlay];
  };
  nixpkgs = import external_sources.nixpkgs nixpkgs_import_args;

  rust = nixpkgs.callPackage ./nix/rust.nix {};
  devShell = nixpkgs.callPackage ./nix/devShell.nix {inherit rust;};

  # TODO: This will be move downwards to each sub-module
  nixfs-rs-bin-cargo = builtins.fromTOML (builtins.readFile ./Cargo.toml);
  nixfs-rs-bin = rust.buildRustPackage {
    pname = nixfs-rs-bin-cargo.package.name;
    inherit (nixfs-rs-bin-cargo.package) version;

    # Approach below, breaks the cargoLock lockFile
    # src = nixpkgs.stdenv.mkDerivation {
    #   name = "${nixfs-rs-bin-cargo.package.name}-src";
    #   src = ./.;
    # };
    src = ./.;

    cargoLock = {lockFile = "./Cargo.lock";};
  };
in {
  inherit devShell nixpkgs nixfs-rs-bin;
}
