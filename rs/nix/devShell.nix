{
  mkShell,
  alejandra,
  cocogitto,
  git,
  helix,
  niv,
  rust,
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
    statix
  ];
}
