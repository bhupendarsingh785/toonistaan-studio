#!/data/data/com.termux/files/usr/bin/bash
# JARVIS for Termux - ek hi baar chalne wala setup
# Chalao:  bash setup.sh
set -u

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}  [OK]${OFF} $*"; }
warn() { echo "${YEL}  [!]${OFF} $*"; }
die()  { echo "${RED}  [X]${OFF} $*"; exit 1; }
step() { echo; echo "${BOLD}$*${OFF}"; }

echo "${BOLD}JARVIS setup - phone only, private${OFF}"
echo "${DIM}Sab kuch aapke phone me rahega. Sirf aapki aawaz/batein Gemini API tak jaati hain.${OFF}"

# 0. Termux check
step "0/6  Termux check"
case "${PREFIX:-}" in
  *com.termux*) ok "Termux environment mil gaya" ;;
  *) die "Ye Termux ke andar nahi chal raha. Termux (F-Droid) kholo, phir bash setup.sh chalao." ;;
esac

DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/jarvis.py" ] || die "jarvis.py isi folder me nahi mila. Dono file ek hi folder me rakho."
ok "jarvis.py mila: $DIR/jarvis.py"

# 1. packages
step "1/6  Packages install (2-4 minute lag sakte hain)"
pkg update -y >/dev/null 2>&1 || warn "pkg update fail hua, aage badh rahe hain"
pkg install -y python termux-api termux-tools >/dev/null 2>&1 \
  && ok "python + termux-api install ho gaye" \
  || warn "pkg install me dikkat - network check karo, phir ye script dobara chalao"

command -v python >/dev/null 2>&1 || die "python install nahi hua. Chalao: pkg install python"
ok "python $(python -c 'import platform;print(platform.python_version())')"

if command -v termux-battery-status >/dev/null 2>&1; then
  ok "Termux:API commands mil gaye"
else
  warn "termux-api commands nahi mile."
  warn "F-Droid se 'Termux:API' app install karo, phir: pkg install termux-api"
fi

# 2. storage
step "2/6  Storage permission"
if [ -d "$HOME/storage" ]; then
  ok "Storage pehle se allowed hai"
else
  echo "  Ab Android 'Allow' ka popup dikhayega - Allow dabao."
  termux-setup-storage || warn "Storage allow nahi hua (photo feature band rahega, baaki sab chalega)"
  sleep 2
fi

# 3. key
step "3/6  Gemini API key (free)"
mkdir -p "$HOME/.jarvis"; chmod 700 "$HOME/.jarvis"
KEYFILE="$HOME/.jarvis/key.txt"
if [ -s "$KEYFILE" ]; then
  ok "Key pehle se saved hai ($(wc -c < "$KEYFILE") bytes)"
else
  echo "  Key yahan se banao (browser me, 1 minute):"
  echo "    ${BOLD}https://aistudio.google.com/apikey${OFF}  ->  Create API key"
  echo "  ${DIM}Key AIza... se shuru hoti hai. Paste karo, screen par kuch nahi dikhega.${OFF}"
  printf "  Paste key: "
  read -rs KEY
  echo
  if [ -z "${KEY:-}" ]; then
    warn "Key khaali - baad me chalao: bash setup.sh"
  else
    printf '%s' "$KEY" > "$KEYFILE"
    chmod 600 "$KEYFILE"
    ok "Key save ho gayi: $KEYFILE (chmod 600)"
  fi
  unset KEY
fi

# 4. launcher + alias
step "4/6  Shortcut banana"
mkdir -p "$HOME/bin"
cat > "$HOME/bin/jarvis" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$DIR" && exec python jarvis.py "\$@"
EOF
chmod +x "$HOME/bin/jarvis"
grep -q 'HOME/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
ok "Ab kahin bhi sirf 'jarvis' likhke chala sakte ho"

# 5. mic permission reminder
step "5/6  Permissions (ek baar haath se)"
cat <<'TXT'
  Android Settings -> Apps -> Termux:API -> Permissions:
      Microphone  : Allow
      Storage     : Allow
      Notifications: Allow (optional)
  Settings -> Apps -> Termux -> Battery -> Unrestricted (warna background me band ho jayega)
TXT

# 6. doctor
step "6/6  Final check"
python "$DIR/jarvis.py" --doctor || true

echo
echo "${BOLD}Ho gaya.${OFF} Chalao:"
echo "    ${BOLD}cd $DIR && python jarvis.py${OFF}     (ya sirf: jarvis)"
echo "${DIM}Text mode (mic ke bina test):  python jarvis.py --text${OFF}"
