#!/data/data/com.termux/files/usr/bin/bash
# JARVIS phone kit - one line installer (Termux)
#   curl -fsSL <this-url> | bash          -> 1.5B model (4GB RAM phone)
#   curl -fsSL <this-url> | bash -s 3     -> 3B model (6GB+ RAM phone)
set -eu
RAW="https://raw.githubusercontent.com/bhupendarsingh785/toonistaan-studio/main/jarvis-kit"
DIR="$HOME/jarvis"
GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'

case "${PREFIX:-}" in *com.termux*) ;; *) echo "Ye Termux ke andar chalao."; exit 1 ;; esac
command -v curl >/dev/null 2>&1 || { echo "Pehle: pkg install -y curl"; exit 1; }

mkdir -p "$DIR"; cd "$DIR"
echo "JARVIS files -> $DIR"
for f in jarvis.py setup.sh setup_local.sh README.md JARVIS_Phone_Setup_Guide.pdf; do
  printf '  %-32s' "$f"
  if curl -fsSL -o "$f.tmp" "$RAW/$f"; then mv "$f.tmp" "$f"; echo "${GREEN}ok${OFF}"; else echo "${RED}fail${OFF}"; exit 1; fi
done
chmod +x jarvis.py setup.sh setup_local.sh 2>/dev/null || true
echo "  ready: $(ls -1 | tr '\n' ' ')"
echo
exec bash "$DIR/setup_local.sh" "$@"
