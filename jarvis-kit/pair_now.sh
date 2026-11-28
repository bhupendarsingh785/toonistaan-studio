#!/data/data/com.termux/files/usr/bin/bash
# Pair JARVIS <-> phone. Sirf do number chahiye: POPUP ka port aur 6-ank code.
set -u
G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; O=$'\033[0m'
ok()  { echo "${G}  [OK]${O} $*"; }
bad() { echo "${R}  [X]${O} $*"; }
wr()  { echo "${Y}  [!]${O} $*"; }

command -v adb >/dev/null 2>&1 || { pkg install -y android-tools >/dev/null 2>&1; }
command -v adb >/dev/null 2>&1 || { bad "adb nahi mila"; exit 1; }

echo "${B}Phone par popup kholo:${O} Settings > System > Developer options > Wireless debugging > 'Pair device with pairing code'"
echo "Popup me:  Wi-Fi pairing code (6 ank)  aur  IP address and port (colon ke baad wala port)"
echo
printf "Dono likho, space se (jaise 37927 123777): "
read -r PORT CODE
[ -n "${PORT:-}" ] && [ -n "${CODE:-}" ] || { bad "dono number chahiye the"; exit 1; }
case "$PORT" in *[!0-9]*) bad "port me sirf ank hone chahiye (aapne '$PORT' diya)"; exit 1 ;; esac
case "$CODE" in *[!0-9]*) bad "code me sirf ank hone chahiye (aapne '$CODE' diya)"; exit 1 ;; esac
[ ${#CODE} -eq 6 ] || wr "code 6 ank ka hota hai, aapne ${#CODE} diye - phir bhi try kar raha hoon"
echo
echo "-> port=$PORT code=$CODE"
echo

IP=$(termux-wifi-connectioninfo 2>/dev/null | grep -o '"ip": *"[^"]*"' | sed 's/.*: *"//;s/"//' | head -1)
[ -z "$IP" ] && IP=$(adb shell ip route 2>/dev/null | awk '{print $9; exit}')
[ -z "$IP" ] && IP=$(ip -4 addr 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 | grep -v '^127' | head -1)
echo "  phone IP: ${IP:-?}"

TRIED=0
for HOST in 127.0.0.1 ${IP:-10.0.0.1}; do
  TRIED=$((TRIED+1))
  echo "  try $TRIED: adb pair $HOST:$PORT"
  OUT=$(adb pair "$HOST:$PORT" "$CODE" 2>&1)
  echo "     $OUT"
  case "$OUT" in
    *"Successfully paired"*) ok "pair ho gaya ($HOST)"; PAIRED="$HOST"; break ;;
  esac
done
[ -n "${PAIRED:-}" ] || { bad "pair nahi hua. Popup dobara kholo (naya code aata hai) aur script turant chalao."; exit 1; }

echo
echo "  connect port dhoondh raha hoon..."
CPORT=""
for i in 1 2 3 4 5; do
  SVC=$(adb mdns services 2>/dev/null)
  CPORT=$(echo "$SVC" | grep -i "connect" | awk '{print $NF}' | head -1)
  [ -n "$CPORT" ] && break
  sleep 2
done
if [ -n "$CPORT" ]; then
  ok "connect: $CPORT"
  adb connect "$CPORT"
else
  wr "connect port khud nahi mila."
  echo "  Wireless debugging ki MAIN screen par 'IP address and port' dekho (jaise 10.198.205.62:42221)"
  printf "  Wahi port likho (ya Enter dabao chhodne ke liye): "
  read -r MANUAL
  if [ -n "${MANUAL:-}" ]; then
    case "$MANUAL" in *:*) CPORT="$MANUAL" ;; *) CPORT="$PAIRED:$MANUAL" ;; esac
    adb connect "$CPORT"
  fi
fi

echo
adb devices
SERIAL=$(adb devices | awk '/device$/{print $1; exit}')
if [ -n "$SERIAL" ]; then
  python "$HOME/jarvis/jarvis.py" --config "adb_serial=$SERIAL" >/dev/null 2>&1 && ok "serial save: $SERIAL"
  echo
  echo "${B}Test:${O}"
  python "$HOME/jarvis/jarvis.py" --adb "echo hello_jarvis" || true
  echo
  echo "Ab: python jarvis.py --text  ->  'youtube band karo'"
else
  wr "device list me nahi aaya. 'adb connect <ip>:<port>' dobara try karo."
fi
