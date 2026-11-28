#!/data/data/com.termux/files/usr/bin/bash
# JARVIS - poora setup ek command se (ADB chhod kar)
set -u
G=$'\033[32m'; Y=$'\033[33m'; B=$'\033[1m'; D=$'\033[2m'; O=$'\033[0m'
ok() { echo "${G}  [OK]${O} $*"; }
wr() { echo "${Y}  [!]${O} $*"; }
step(){ echo; echo "${B}$*${O}"; }

DIR="$HOME/jarvis"
[ -f "$DIR/jarvis.py" ] || { echo "Pehle: mkdir -p ~/jarvis && cd ~/jarvis && unzip zip"; exit 1; }
cd "$DIR" || exit 1

step "1/5  Packages"
pkg install -y python termux-api >/dev/null 2>&1 && ok "python + termux-api" || wr "pkg install me dikkat"

step "2/5  Data vault + projects"
mkdir -p "$DIR/data" "$DIR/projects" "$DIR/models"
ok "data vault: $DIR/data"
ok "projects:   $DIR/projects"

step "3/5  Speed + voice settings"
python jarvis.py --speed quality >/dev/null 2>&1 && ok "speed=quality (madhur awaaz)"
python jarvis.py --config providers=groq,gemini,openrouter,local >/dev/null 2>&1 && ok "chain: groq -> gemini -> openrouter -> local"
python jarvis.py --config briefing=true >/dev/null 2>&1 && ok "briefing on"

step "4/5  Shortcuts + boot"
bash "$DIR/setup_widget.sh" >/dev/null 2>&1 && ok "home screen shortcuts" || wr "widget script fail"
bash "$DIR/setup_boot.sh" >/dev/null 2>&1 && ok "boot autostart" || wr "boot script fail"

step "5/5  Final check"
python jarvis.py --doctor || true

echo
echo "${B}Ho gaya. Roz ke 2 command:${O}"
echo "    bash ~/jarvis/start.sh          ${D}# panel chalu + Chrome khulega${O}"
echo "    python ~/jarvis/jarvis.py --update   ${D}# naya version aaye to${O}"
echo
echo "${D}ADB (app band karna) baad me: bash ~/pair_now.sh${O}"
