#!/data/data/com.termux/files/usr/bin/bash
# JARVIS local brain setup - permanent free, no API key, no internet, no dependency
# Chalao:  bash setup_local.sh            (halka model ~1.1 GB, 4GB RAM phone)
#          bash setup_local.sh 3          (behtar model ~2.1 GB, 6GB+ RAM phone)
#          bash setup_local.sh --build    (llama-server khud compile karo - link error ka pakka fix)
set -u

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}  [OK]${OFF} $*"; }
warn() { echo "${YEL}  [!]${OFF} $*"; }
die()  { echo "${RED}  [X]${OFF} $*"; exit 1; }
step() { echo; echo "${BOLD}$*${OFF}"; }

SIZE=1.5
FORCE_BUILD=0
for a in "$@"; do
  case "$a" in
    3|30) SIZE=3 ;;
    1.5|15) SIZE=1.5 ;;
    --build|build) FORCE_BUILD=1 ;;
    *) die "Use: bash setup_local.sh [1.5|3] [--build]" ;;
  esac
done

case "${PREFIX:-}" in
  *com.termux*) ;;
  *) die "Ye Termux ke andar chalao." ;;
esac

DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/jarvis.py" ] || die "jarvis.py isi folder me hona chahiye."
MODELS="$DIR/models"; DATA="$DIR/data"
mkdir -p "$MODELS" "$DATA"

echo "${BOLD}JARVIS local brain - phone me hi model${OFF}"
echo "${DIM}Zero internet, zero API key, zero kharcha. Model sirf ek baar download hota hai.${OFF}"

server_ok() {
  llama-server --version >/dev/null 2>&1
}

build_from_source() {
  step "llama.cpp source se build (15-40 minute, ek baar)"
  echo "  ${DIM}Phone charge par rakho, screen on rakho, Termux band na karo.${OFF}"
  pkg install -y git cmake make clang >/dev/null 2>&1 || die "build tools install nahi hue"
  if [ ! -d "$HOME/llama.cpp/.git" ]; then
    git clone --depth 1 https://github.com/ggerganov/llama.cpp "$HOME/llama.cpp" || die "git clone fail (internet?)"
  fi
  cd "$HOME/llama.cpp" || die "llama.cpp folder nahi mila"
  cmake -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF >/dev/null 2>&1 \
    || die "cmake fail - screenshot bhejo"
  cmake --build build --config Release -j"$(nproc)" >/dev/null 2>&1 \
    || die "build fail - screenshot bhejo"
  mkdir -p "$PREFIX/bin"
  if [ -f build/bin/llama-server ]; then
    cp build/bin/llama-server "$PREFIX/bin/llama-server"
  elif [ -f build/bin/server ]; then
    cp build/bin/server "$PREFIX/bin/llama-server"
  else
    die "binary nahi bana - screenshot bhejo"
  fi
  chmod +x "$PREFIX/bin/llama-server"
  cd "$DIR" || true
  server_ok && ok "llama-server build ho gaya" || die "build hua par chal nahi raha - screenshot bhejo"
}

# 1. tools + working llama-server
step "1/5  llama.cpp (model chalane wala engine)"
pkg install -y curl >/dev/null 2>&1 || warn "curl install me dikkat"
command -v curl >/dev/null 2>&1 || die "curl nahi mila: pkg install curl"

if [ "$FORCE_BUILD" = "1" ]; then
  build_from_source
elif command -v llama-server >/dev/null 2>&1 && server_ok; then
  ok "llama-server chal raha hai: $(llama-server --version 2>&1 | head -1)"
else
  if ! command -v llama-server >/dev/null 2>&1; then
    echo "  llama-cpp install kar raha hoon..."
    pkg install -y llama-cpp >/dev/null 2>&1 || warn "package nahi mila"
  fi
  if command -v llama-server >/dev/null 2>&1 && server_ok; then
    ok "llama-server install ho gaya"
  else
    warn "llama-server toota hua hai (link error) - libc++ update try kar raha hoon"
    pkg update -y >/dev/null 2>&1 || true
    pkg upgrade -y >/dev/null 2>&1 || true
    pkg install -y libc++ libandroid-support >/dev/null 2>&1 || true
    if command -v llama-server >/dev/null 2>&1 && server_ok; then
      ok "libc++ update se theek ho gaya"
    else
      warn "package wala binary theek nahi hua - source se build karunga"
      build_from_source
    fi
  fi
fi
server_ok || die "llama-server kaam nahi kar raha. Chalao: bash setup_local.sh --build"

# 2. model
step "2/5  Model download (ek baar, phir hamesha offline)"
if [ "$SIZE" = "3" ]; then
  URL="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
  NEED_GB=2.1; RAM_GB=6
else
  URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
  NEED_GB=1.1; RAM_GB=4
fi
MODEL="$MODELS/model.gguf"
MIN_BYTES=300000000

if [ -f "$MODEL" ] && [ "$(stat -c %s "$MODEL" 2>/dev/null || echo 0)" -gt "$MIN_BYTES" ]; then
  ok "model pehle se hai: $MODEL ($(du -h "$MODEL" | cut -f1))"
else
  [ -f "$MODEL" ] && warn "purana model file adhoora tha - dobara download"
  FREE=$(df -Pk "$MODELS" | awk 'NR==2 {print int($4/1024/1024)}')
  echo "  Chahiye: ${NEED_GB} GB  |  free: ${FREE} GB  |  phone RAM: ${RAM_GB} GB+ behtar"
  [ "$FREE" -lt 3 ] && warn "jagah kam hai - purani files hatao, phir dobara chalao"
  echo "  Download shuru (resume support hai, ruk jaye to dobara chalao):"
  curl -L --fail --continue-at - --progress-bar -o "$MODEL.part" "$URL" \
    || die "download fail - internet check karo, phir yahi command dobara chalao"
  mv "$MODEL.part" "$MODEL"
  ok "model ready: $MODEL ($(du -h "$MODEL" | cut -f1))"
fi

# 3. data folder
step "3/5  Aapka data folder"
echo "  $DATA"
echo "  Yahan apni files rakho: .txt .md .csv .json .srt .pdf"
if [ -z "$(ls -A "$DATA" 2>/dev/null)" ]; then
  cat > "$DATA/README-data.txt" <<'TXT'
Is folder me apni files rakho - notes, scripts, ideas, sponsor list, kuch bhi.
Supported: .txt .md .csv .json .srt .pdf
Phir chalao:  python jarvis.py --index
JARVIS jawab dete waqt inhi files me se relevant hisse padhta hai.
Sab kuch phone me hi rehta hai, koi upload nahi.
TXT
  warn "data folder khaali tha - ek README bana diya"
else
  ok "$(find "$DATA" -type f | wc -l) file mili"
fi

# 4. brain switch + index
step "4/5  Brain local par switch + index"
python "$DIR/jarvis.py" --brain local || warn "--brain local fail"
python "$DIR/jarvis.py" --index || true

# 5. check
step "5/5  Final check"
python "$DIR/jarvis.py" --doctor || true

echo
echo "${BOLD}Ho gaya. Ab internet band karke bhi chala sakte ho:${OFF}"
echo "    cd $DIR && python jarvis.py --text"
echo "    python jarvis.py --once \"mere notes ke hisaab se batao\""
echo
echo "${DIM}Wapas Gemini par jaana ho:  python jarvis.py --brain gemini${OFF}"
echo "${DIM}Google Drive se data laana ho:  pkg install rclone; rclone config  (free, apna account)${OFF}"
