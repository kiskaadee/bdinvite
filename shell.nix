{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "bdinvite-dev";

  buildInputs = with pkgs; [
    nodejs
    biome
    uv
    python311
  ];

  shellHook = ''
    echo "🎂 bdinvite development shell loaded"
    echo "   Node: $(node --version 2>/dev/null || echo 'not found')"
    echo "   Biome: $(biome --version 2>/dev/null || echo 'not found')"
    echo "   uv: $(uv --version 2>/dev/null || echo 'not found')"
  '';
}
