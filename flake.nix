{
  description = "A Nix-flake-based C/C++ development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/25.05";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    fenix = {
      url = "github:nix-community/fenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs @ {
    flake-parts,
    fenix,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = [
        "x86_64-linux"
        "aarch64-darwin"
      ];

      perSystem = {
        pkgs,
        system,
        ...
      }: {
        formatter = pkgs.alejandra;

        devShells.default = pkgs.mkShell.override {stdenv = pkgs.llvmPackages_13.stdenv;} {
          hardeningDisable = ["fortify"];
          packages = with pkgs;
            [
              just
              cmake
              z3
              stp
              gllvm
              wllvm
              graphviz
              linuxHeaders
              gperftools
              sqlite
              libxml2
              openssl
              libpsl
              ninja
              cppcheck
              lit
              texinfo
              unzip
              uv
            ]
            ++ (with pkgs.llvmPackages_13; [
              libllvm
              libcxx
              clang-tools
            ])
            ++ (with pkgs.python312Packages; [
              distutils
              tabulate
              z3-solver
            ])
            ++ [
              (fenix.packages.${system}.stable.toolchain)
            ];
          env = {
            # Z3_LIBRARY_PATH = "${pkgs.z3.dev}/lib";
            OUT_DIR = "/tmp/klee-out";
          };
        };
      };
    };
}
