#!/data/data/com.termux/files/usr/bin/bash
# JARVIS ko poora phone control dene ke liye ek baar ka setup (wireless debugging)
set -u
BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}  [OK]${OFF} $*"; }
warn() { echo "${YEL}  [!]${OFF} $*"; }
die()  { echo "${RED}  [X]${OFF} $*"; exit 1; }

case "${PREFIX:-}" in *com.termux*) ;; *) die "Termux ke andar chalao" ;; esac

echo "${BOLD}Phone control setup (self-ADB)${OFF}"
echo "${DIM}Iske baad JARVIS kisi bhi app ko band/chalu kar sakta hai, pause/play, back, home,${OFF}"
echo "${DIM}screen padhna, tap karna - sab bina root. Ek baar ka kaam.${OFF}"

echo
echo "${BOLD}Step 1 - Developer options${OFF}"
cat <<'TXT'
  Settings -> About phone -> "Build number" par 7 baar tap karo
  Settings -> System -> Developer options -> ON
TXT

echo
echo "${BOLD}Step 2 - Wireless debugging ON${OFF}"
cat <<'TXT'
  Settings -> System -> Developer options -> Wireless debugging -> ON
  (Wi-Fi par rehna zaroori hai)
TXT

echo
echo "${BOLD}Step 3 - adb install${OFF}"
pkg install -y android-tools >/dev/null 2>&1 || die "android-tools install nahi hua"
command -v adb >/dev/null 2>&1 && ok "adb ready" || die "adb nahi mila"

echo
echo "${BOLD}Step 4 - Pair${OFF}"
echo "  Wireless debugging screen me 'Pair device with pairing code' dabao."
echo "  Wahan 6-digit code aur ek port dikhega (jaise 127.0.0.1:37123)."
read -r -p "  Pairing port (sirf number): " PPORT
read -r -p "  6-digit code: " PCODE
if [ -n "$PPORT" ] && [ -n "$PCODE" ]; then
  adb pair "127.0.0.1:$PPORT" "$PCODE" || warn "pair fail - port/code dobara check karo"
else
  warn "port/code khaali - step 4 chhod diya"
fi

echo
echo "${BOLD}Step 5 - Connect${OFF}"
echo "  Wireless debugging ki main screen par 'IP address & Port' dikhega (jaise 192.168.1.5:40001)."
echo "  Wahi port daalo (ya sirf number)."
read -r -p "  Connect port: " CPORT
if [ -n "$CPORT" ]; then
  case "$CPORT" in *:*) TARGET="$CPORT" ;; *) TARGET="127.0.0.1:$CPORT" ;; esac
  adb connect "$TARGET" || warn "connect fail"
  sleep 2
  adb devices
  if adb devices | grep -q "device$"; then
    SERIAL=$(adb devices | awk '/device$/{print $1; exit}')
    python "$HOME/jarvis/jarvis.py" --config "adb_serial=$SERIAL" >/dev/null 2>&1 \
      && ok "serial save ho gaya: $SERIAL" || warn "serial save nahi hua (manually: --config adb_serial=$SERIAL)"
  else
    warn "device connect nahi hua"
  fi
else
  warn "port khaali - connect chhod diya"
fi

echo
echo "${BOLD}Step 6 - Test${OFF}"
python "$HOME/jarvis/jarvis.py" --adb "echo hello_jarvis" || true
echo
echo "  Try karo:  python jarvis.py --adb \"input keyevent 3\"   (home button)"
echo "  Phir bolo: python jarvis.py --text  ->  'youtube band karo'"
echo
echo "${DIM}Note: phone restart hone par wireless debugging band ho jata hai -${OFF}"
echo "${DIM}tab sirf 'adb connect <ip>:<port>' dobara chala lena (pair dobara nahi).${OFF}"
