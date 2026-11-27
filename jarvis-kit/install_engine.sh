#!/data/data/com.termux/files/usr/bin/bash
# JARVIS engine - ready-made llama-server binary (phone par koi compile nahi)
set -eu
RAW="https://raw.githubusercontent.com/bhupendarsingh785/toonistaan-studio/main/jarvis-kit"
DIR="$HOME/jarvis"
GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'

case "${PREFIX:-}" in *com.termux*) ;; *) echo "Ye Termux ke andar chalao."; exit 1 ;; esac
command -v curl >/dev/null 2>&1 || { echo "Pehle: pkg install -y curl"; exit 1; }
[ -f "$DIR/jarvis.py" ] || { echo "$DIR/jarvis.py nahi mila"; exit 1; }

ENG="$DIR/engine"
mkdir -p "$ENG"
echo "${BOLD}Ready-made engine download (koi compile nahi, ~9.5 MB)${OFF}"
if ! curl -fL --progress-bar -o "$DIR/engine.tar.gz" "$RAW/bin/engine-android-arm64.tar.gz"; then
  echo "${RED}download fail${OFF} - internet check karo"; exit 1
fi
tar -xzf "$DIR/engine.tar.gz" -C "$ENG" || { echo "${RED}extract fail${OFF}"; exit 1; }
rm -f "$DIR/engine.tar.gz"
chmod +x "$ENG/llama-server"
export LD_LIBRARY_PATH="$ENG"

echo "  jarvis.py update (naya version)..."
if curl -fsSL -o "$DIR/jarvis.py.new" "$RAW/jarvis.py"; then
  mv "$DIR/jarvis.py.new" "$DIR/jarvis.py"
  echo "  ${GREEN}[OK]${OFF} jarvis.py update ho gaya"
else
  rm -f "$DIR/jarvis.py.new"
  echo "  ${YEL}[!]${OFF} jarvis.py update fail - purana hi rahega"
fi
echo
if OUT=$("$ENG/llama-server" --version 2>&1) && [ -n "$OUT" ]; then
  echo "$OUT" | head -2
  echo "${GREEN}  [OK]${OFF} engine chal raha hai"
else
  echo "${YEL}  [!]${OFF} engine chal nahi raha"
  echo "$OUT" | head -3
  exit 1
fi
echo
python "$DIR/jarvis.py" --brain local || true
python "$DIR/jarvis.py" --doctor || true
echo
echo "${BOLD}Ab chalao:${OFF}  cd $DIR && python jarvis.py --text"
