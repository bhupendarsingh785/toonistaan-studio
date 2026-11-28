#!/data/data/com.termux/files/usr/bin/bash
# JARVIS ek command se: wakelock + browser panel + Chrome kholna
set -u
cd "$HOME/jarvis" || { echo "~/jarvis nahi mila"; exit 1; }
termux-wake-lock 2>/dev/null
command -v python >/dev/null 2>&1 || { echo "python nahi hai: pkg install python"; exit 1; }
echo "JARVIS shuru ho raha hai..."
exec python jarvis.py --serve "${1:-8080}"
