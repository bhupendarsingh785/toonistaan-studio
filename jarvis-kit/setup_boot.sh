#!/data/data/com.termux/files/usr/bin/bash
# Phone start hote hi JARVIS ka browser panel chalu ho jaye (Termux:Boot)
set -u
G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; O=$'\033[0m'
ok()  { echo "${G}  [OK]${O} $*"; }
wr()  { echo "${Y}  [!]${O} $*"; }
case "${PREFIX:-}" in *com.termux*) ;; *) echo "Termux ke andar chalao"; exit 1 ;; esac
[ -f "$HOME/jarvis/jarvis.py" ] || { echo "$HOME/jarvis/jarvis.py nahi mila"; exit 1; }

mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/10-jarvis.sh" <<'S'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
sleep 12
cd "$HOME/jarvis" || exit 0
python jarvis.py --serve 8080 >> "$HOME/jarvis/boot.log" 2>&1
S
chmod +x "$HOME/.termux/boot/10-jarvis.sh"
ok "boot script ban gaya: ~/.termux/boot/10-jarvis.sh"
echo
echo "  Ab F-Droid se ${Y}Termux:Boot${O} install karo aur ek baar khol do."
echo "  Uske baad phone start hote hi panel taiyar hoga: http://127.0.0.1:8080"
echo "  Log: ~/jarvis/boot.log"
