#!/data/data/com.termux/files/usr/bin/bash
# JARVIS <-> phone pairing, auto port detect (sirf 6-digit code daalna hai)
set -u
BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}  [OK]${OFF} $*"; }
warn() { echo "${YEL}  [!]${OFF} $*"; }
die()  { echo "${RED}  [X]${OFF} $*"; exit 1; }

command -v adb >/dev/null 2>&1 || pkg install -y android-tools >/dev/null 2>&1
command -v adb >/dev/null 2>&1 || die "adb nahi mila: pkg install android-tools"

adb start-server >/dev/null 2>&1
echo "${BOLD}Ports dhoondh raha hoon (mDNS)...${OFF}"
PAIR=""; CONN=""
for i in 1 2 3; do
  SVC=$(adb mdns services 2>/dev/null)
  PAIR=$(echo "$SVC" | grep -i "pairing" | awk '{print $NF}' | head -1)
  CONN=$(echo "$SVC" | grep -i "connect" | awk '{print $NF}' | head -1)
  [ -n "$PAIR" ] && [ -n "$CONN" ] && break
  echo "  (try $i - pairing popup khula rakho, phone par Wireless debugging ON ho)"
  sleep 2
done

if [ -z "$PAIR" ]; then
  warn "pairing service nahi mili. Phone par 'Pair device with pairing code' popup kholo, phir ye script dobara chalao."
  echo "  (Agar phir bhi na mile, manually: adb pair <ip>:<port> <code>)"
  exit 1
fi
ok "pairing port: $PAIR"
[ -n "$CONN" ] && ok "connect port: $CONN" || warn "connect port nahi mila"

echo
printf "  Popup ke 6 ank daalo: "
read -r CODE
[ -n "$CODE" ] || die "code khaali"

echo
if adb pair "$PAIR" "$CODE"; then
  ok "pair ho gaya"
else
  die "pair fail - code expire ho gaya hoga. Popup dobara kholo (naya code) aur script turant chalao."
fi

if [ -z "$CONN" ]; then
  printf "  Connect port daalo (Wireless debugging screen se): "
  read -r CPORT
  case "$CPORT" in *:*) CONN="$CPORT" ;; *) CONN="127.0.0.1:$CPORT" ;; esac
fi

adb connect "$CONN" && ok "connect: $CONN"
sleep 1
adb devices
SERIAL=$(adb devices | awk '/device$/{print $1; exit}')
if [ -n "$SERIAL" ]; then
  python "$HOME/jarvis/jarvis.py" --config "adb_serial=$SERIAL" >/dev/null 2>&1 && ok "serial save: $SERIAL"
  echo
  echo "${BOLD}Test:${OFF}"
  python "$HOME/jarvis/jarvis.py" --adb "echo hello_jarvis" || true
  echo
  echo "Ab bolo: python jarvis.py --text  ->  'youtube band karo'"
else
  warn "device list me nahi aaya - 'adb connect' dobara try karo"
fi
