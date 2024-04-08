{
  makeRustPlatform,
  rust-bin,
  ...
}: let
  rustBin = rust-bin.stable.latest.default.override {
    extensions = ["rust-src"];
  };
  rustPlatform = makeRustPlatform {
    cargo = rustBin;
    rustc = rustBin;
  };
  inherit (rustPlatform) buildRustPackage;
in {
  inherit rustBin rustPlatform buildRustPackage;
}
