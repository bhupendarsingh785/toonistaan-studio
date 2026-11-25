# ASTRA Awaaz System — asli code

Ye repo ka poora chalta hua code hai. ZERO baseline: `baseline/zero/`.

## Sabse pehle (5 command)
```bash
pip install -r requirements.txt
python tools/cast_build.py baseline/zero/script.txt out.mp3   # kahani banao
python tools/zero_baseline.py --check out.mp3                 # zero se compare
python checker/voice_checker.py --file out.mp3                # jitter/shimmer/HNR
python tools/kram.py jaanch                                   # structure check
```

## Zaroori files
| File | Kaam |
|---|---|
| `tools/cast_build.py` | har kirdaar ki awaaz → kahani (ZERO pipeline) |
| `tools/clarity.py` | 100 Hz HPF + exciter + presence + de-ess |
| `tools/zero_baseline.py` | zero se neeche jaane se rokta hai |
| `checker/voice_checker.py` | insaan ke baseline par naap |
| `checker/audio_gate.py` | scan → fix → rescan → release/block |
| `tools/kram.py` | structure / level / collision |
| `tools/system_audit.py` | orphan / collision / wire |
| `tools/regression.py` | 10 check ka test |
| `engines/` | EDGE, ELEVENLABS, ESPEAK, PIPER, SARVAM configs |
| `baseline/zero/zero.json` | zero ki exact settings |
| `CODE-MAP.md` | har file + function ki list |
| `PIPELINE.md` | pipeline ka niyam (locked) |

## Awaaz ke model
`/scratch/work/voices/hi_IN-priyamvada-medium.onnx` (female 207 Hz) aur
`hi_IN-pratham-medium.onnx` (male 97 Hz) — piper ke Hindi voices. Ye bade files hain,
isliye zip me nahi hain; `tools/voice_provider.py` inhe khud dhoondh leta hai.
