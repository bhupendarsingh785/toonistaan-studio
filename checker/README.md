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
