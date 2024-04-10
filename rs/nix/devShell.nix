{
  mkShell,
  alejandra,
  cocogitto,
  fuse3,
  git,
  helix,
  niv,
  pkg-config,
  rust,
  rust-analyzer,
  statix,
}:
mkShell {
  name = "nixfs-dev-shell";
  packages = [
    alejandra
    cocogitto
    git
    helix
    niv
    rust.rustBin
    rust-analyzer
    statix
    # crate: fuser deps
    fuse3
    pkg-config
  ];
}
