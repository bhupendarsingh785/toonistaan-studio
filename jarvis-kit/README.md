# JARVIS for Termux - private, phone-only

Aapka apna personal assistant, sirf aapke Android phone me. Laptop nahi chahiye.
Poora code ek hi file (`jarvis.py`) me hai - padho, badlo, apna banao.

## Andar kya hai

| File | Kaam |
|---|---|
| `jarvis.py` | Main assistant. Aawaz sunta hai, Gemini se jawab laata hai, phone ke kaam karta hai, yaadein rakhta hai. |
| `setup.sh` | Ek baar chalne wala setup: packages, permissions, API key, `jarvis` shortcut, final check. |
| `setup_local.sh` | Permanent free mode: model phone me download karke Gemini/API key ki zarurat khatam. Offline chalega. |
| `JARVIS_Phone_Setup_Guide.pdf` | Poora guide (Hinglish, 9 page) - screenshots ki jagah exact steps aur troubleshooting. |

## 4 line me setup

```bash
pkg install -y unzip
mkdir -p ~/jarvis && cd ~/jarvis
unzip /sdcard/Download/JARVIS_Phone_Kit.zip
bash setup.sh
```

`setup.sh` khud key maangega. Free key: https://aistudio.google.com/apikey

## Chalana

```bash
python jarvis.py            # aawaz wala mode: Enter dabao, bolo
python jarvis.py --text     # mic ke bina, type karke
python jarvis.py --doctor   # kuch kaam na kare to pehle yahi chalao
```

## Permanent free mode (koi API key nahi)

**Aasan raasta (phone par koi compile nahi)** - ready-made engine:

```bash
cd ~/jarvis && curl -fsSL https://raw.githubusercontent.com/bhupendarsingh785/toonistaan-studio/main/jarvis-kit/install_engine.sh | bash
```

**Ya khud compile karna ho** (20-45 min, phone par load):

```bash
cd ~/jarvis
bash setup_local.sh        # 1.1 GB model, 4GB RAM phone
bash setup_local.sh 3      # 2.1 GB model, 6GB+ RAM phone
```

Phir:

```bash
python jarvis.py --brain local     # free, offline, private
python jarvis.py --brain gemini    # wapas cloud brain
```

Model ek baar download hota hai, uske baad internet/key/kharcha kuch nahi.
Sach: 1.5B local model Gemini jitna smart nahi hota - simple kaam, phone control
aur aapke notes ke sawaal theek, mushkil soch kamzor.

## Apna data jodna

Apni files `~/jarvis/data/` me daalo (`.txt .md .csv .json .srt .pdf`), phir:

```bash
cp /sdcard/Download/notes.txt ~/jarvis/data/
python jarvis.py --index          # kya padha gaya, wo dikhata hai
```

Jawab dete waqt JARVIS inhi files me se relevant hisse padhta hai. Sab local.
Drive se sync: `pkg install rclone && rclone config`.

## Zaroori

- Termux aur Termux:API dono **F-Droid** se (Play Store wala purana hai).
- Termux:API ko Microphone + Storage permission do.
- Termux ki battery setting **Unrestricted** karo.
- Key `~/.jarvis/key.txt` me rehti hai (chmod 600). Kisi ko na do.

## Privacy

Aawaz/text sirf Gemini API tak jaata hai (jawab banane ke liye). Notes, yaadein,
logs aur key sirf aapke phone me `~/.jarvis/` me rehte hain. Koi telemetry nahi.

## License

Ye kit aapki hai - personal use ke liye, jitna chahe badlo.
(Laptop wala Mark-LVI/Mark-LVII alag project hai, uska license CC BY-NC 4.0 hai.)
