# Voice Checker (ALAG tool — system ka hissa nahi)

Ye tool **system se alag** rakha gaya hai: na kram me, na pipeline me, na regression me.
Sirf apni audio ko insaan ke paimane par jaanchne ke liye.

```bash
python checker/voice_checker.py --file out.mp3          # ek file
python checker/voice_checker.py --audit-dir /scratch/output   # sab files
python checker/voice_checker.py --learn-baseline /path/clips  # asli insaan se baseline
```

Naap: sur (F0), jitter, shimmer, HNR, raftaar, rukna, jhatke, clipping.
Baseline `checker/voice-baseline.json` me rehta hai (asli recordings se seekha hua).
Report: `checker/voice-check-report.json`.

## audio_gate.py — RELEASE GATE (automatic silsila)

Jab tak audio insaan jaisi na bane, **release nahi hoti**.

```bash
python checker/audio_gate.py --file in.wav --script story.txt --release out.mp3
python checker/audio_gate.py --selftest          # robot-jaisi awaaz par BLOCK dikhata hai
```

Silsila: **SCAN → FIX (level 1..4) → RESCAN → ... → RELEASE / BLOCK**
- Naap: jitter, shimmer, HNR, sur ka failaav (flat = robot), buzz (2-5 kHz), rukna,
  rukne me variety, raftaar, jhatke, clipping, background (mausam), **bhaav-match** (script se)
- Thresholds asli insaan ki recordings se naape hue hain
- Har koshish `checker/gate-log.jsonl` me likhi jaati hai
- PASS na ho to file **output me nahi jaati** (exit code 2)
