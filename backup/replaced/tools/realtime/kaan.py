"""
Kaan (sunna) — line bante hi use sun kar likhna (ASR), 100% local.

FasterWhisperEar : faster-whisper, int8, CPU 2 core par bhi. Hindi, beam 1, temperature 0,
                   pichhla text yaad NAHI (condition_on_previous_text=False) aur koi prompt nahi —
                   taaki ASR khud "sahi spelling" na bhar de (warna galti chhup jaati hai).
                   Har shabd ki probability: < 0.45 = "shak" (ASR ko khud bharosa nahi = awaaz saaf nahi).
CacheEar         : ek hi audio dobara na suno (hash -> result), aapke asr_cache jaisa.
SimulatedEar     : SIRF TEST ke liye. Ek nakli "engine ki kamzori" profile se galtiyan banata hai,
                   taaki sudhaar-loop ko bina model ke jaancha ja sake. Asli kaam me kabhi mat lagao.
"""
from __future__ import annotations
import hashlib, json, re, time
from pathlib import Path
import numpy as np

class FasterWhisperEar:
    name = "faster-whisper"
    def __init__(self, model="small", device="auto", compute_type="int8", cpu_threads=2, download_root=None):
        from faster_whisper import WhisperModel
        self.m = WhisperModel(model, device=device, compute_type=compute_type, cpu_threads=cpu_threads, download_root=download_root)
        self.model = model

    def hear(self, wav, sr, hint=None):
        t = time.time()
        if sr != 16000:
            import librosa
            wav = librosa.resample(wav.astype(np.float32), orig_sr=sr, target_sr=16000)
        segs, _ = self.m.transcribe(wav.astype(np.float32), language="hi", beam_size=1, temperature=0.0,
                                    condition_on_previous_text=False, word_timestamps=True, vad_filter=False,
                                    without_timestamps=False)
        words, text = [], []
        for s in segs:
            text.append(s.text)
            for w in (s.words or []):
                words.append({"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 3)})
        return {"text": " ".join(text).strip(), "words": words, "ms": int((time.time() - t) * 1000), "ear": f"{self.name}:{self.model}"}

class CacheEar:
    def __init__(self, ear, cache_dir):
        self.ear = ear; self.dir = Path(cache_dir); self.dir.mkdir(parents=True, exist_ok=True)
        self.name = f"cache({ear.name})"
    def hear(self, wav, sr, hint=None):
        h = hashlib.sha1(np.asarray(wav, np.float32).tobytes() + str(sr).encode()).hexdigest()[:16]
        f = self.dir / f"{h}.json"
        if f.exists():
            r = json.loads(f.read_text(encoding="utf-8")); r["ms"] = 0; r["cached"] = True; return r
        r = self.ear.hear(wav, sr, hint); f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8"); return r

class SimulatedEar:
    """TEST-ONLY. 'hint' = TTS ko diya gaya text. Profile ke niyam us text me jo roop dhoondhte hain,
    usi jagah galti 'sunai' deti hai — jaise asli engine ki G2P kamzori. Respelling se roop hata to galti hat jaati hai."""
    name = "SIMULATED"
    def __init__(self, profile, rate_of=None):
        self.rules = [(re.compile(r["pattern"]), r["heard"], r.get("min_speed")) for r in profile["rules"]]
        self.rate_of = rate_of or (lambda: 1.0)
    def hear(self, wav, sr, hint=None):
        t0 = time.time(); txt = hint or ""          # raw: engine ko jo roop mila wahi (NFC nahi)
        txt = txt.replace("‌", "")
        speed = self.rate_of()
        for rx, heard, min_speed in self.rules:
            if min_speed and speed < min_speed: continue          # dheema bolne par yeh galti nahi hoti
            txt = rx.sub(heard, txt)
        txt = re.sub(r"(\S)्ह", lambda m: {"क": "ख", "ग": "घ", "द": "ध", "ब": "भ", "प": "फ", "त": "थ", "च": "छ", "ज": "झ"}.get(m.group(1), m.group(1) + "ह"), txt)
        txt = re.sub(r"[,]", " ", txt)
        words = [{"w": w, "start": 0, "end": 0, "p": 0.9} for w in txt.split()]
        return {"text": txt, "words": words, "ms": int((time.time() - t0) * 1000) + 5, "ear": "SIMULATED"}

def make_ear(kind="auto", **kw):
    """auto: faster-whisper mile to woh, warna saaf error (chupchap nakli mat chalao)."""
    if kind in ("auto", "faster-whisper"):
        return FasterWhisperEar(**kw)
    raise ValueError(f"ear '{kind}' nahi pata")
