#!/data/data/com.termux/files/usr/bin/bash
# Home screen par JARVIS ka one-tap icon (Termux:Widget)
set -u
G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; D=$'\033[2m'; O=$'\033[0m'
ok()  { echo "${G}  [OK]${O} $*"; }
wr()  { echo "${Y}  [!]${O} $*"; }
die() { echo "${R}  [X]${O} $*"; exit 1; }

case "${PREFIX:-}" in *com.termux*) ;; *) die "Termux ke andar chalao" ;; esac
[ -f "$HOME/jarvis/jarvis.py" ] || die "$HOME/jarvis/jarvis.py nahi mila"

mkdir -p "$HOME/.shortcuts" "$HOME/.shortcuts/tasks"
chmod 700 "$HOME/.shortcuts"

# 1) voice mode (tap -> bolo)
cat > "$HOME/.shortcuts/JARVIS" <<'S'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/jarvis" || exit 1
termux-wake-lock 2>/dev/null
exec python jarvis.py
S
chmod +x "$HOME/.shortcuts/JARVIS"

# 2) text mode
cat > "$HOME/.shortcuts/JARVIS Text" <<'S'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/jarvis" || exit 1
termux-wake-lock 2>/dev/null
exec python jarvis.py --text
S
chmod +x "$HOME/.shortcuts/JARVIS Text"

# 3) briefing (sirf sunne ke liye)
cat > "$HOME/.shortcuts/JARVIS Briefing" <<'S'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/jarvis" || exit 1
exec python jarvis.py --briefing
S
chmod +x "$HOME/.shortcuts/JARVIS Briefing"

# 4) research (popup me sawaal)
cat > "$HOME/.shortcuts/tasks/JARVIS Research" <<'S'
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/jarvis" || exit 1
Q=$(termux-dialog text -t "Research kya karna hai?" -i "jaise: ISRO ka agla mission" | grep -o '"text": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
[ -n "$Q" ] && python jarvis.py --research "$Q"
S
chmod +x "$HOME/.shortcuts/tasks/JARVIS Research"

ok "Shortcuts ban gaye:"
ls -1 "$HOME/.shortcuts" "$HOME/.shortcuts/tasks" | sed 's/^/    /'

echo
echo "${B}Ab widget lagao (ek baar):${O}"
cat <<'TXT'
  1. F-Droid se "Termux:Widget" install karo
  2. Home screen par khali jagah par long-press -> Widgets
  3. "Termux:Widget" dhoondho -> 1x1 widget home screen par rakho
  4. Widget par tap karo -> list me "JARVIS" chuno
TXT

echo
echo "${B}Tip:${O} ${D}Widget ek tap me naya Termux session khol deta hai, phir Enter dabao aur bolo.${O}"
echo "${B}Continuous baat:${O} ${D}python jarvis.py --config auto_loop=true  (Enter ki zarurat nahi, lagataar sunta rahega)${O}"
