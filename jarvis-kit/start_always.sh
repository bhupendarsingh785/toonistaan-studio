#!/data/data/com.termux/files/usr/bin/bash
# JARVIS hamesha chalta rahe - wakelock + auto restart
set -u
cd "$HOME/jarvis" || { echo "~/jarvis nahi mila"; exit 1; }
termux-wake-lock 2>/dev/null
pkill -f "jarvis.py --always" 2>/dev/null
while true; do
  python jarvis.py --always
  code=$?
  echo "  (JARVIS ruk gaya, 5 second me dobara...)"
  termux-notification --title "JARVIS restart" --content "Dobara shuru ho raha hoon" --id jarvis 2>/dev/null
  sleep 5
done
