#!/usr/bin/env python3
"""awaaz_bank.py — apni ASLI awaazon ka bank (har kirdaar, har bhaav) + IndicF5 se clone.

Ek kirdaar = ek zaroori recording (saadharan) + jitne chaho bhaav (hansna, gussa, udaas, dar,
dheere, pukaar, pyaar). Har recording ki turant jaanch: shor, goonj ka andaza, phatna (clip),
lambai, bolne ka hissa, bijli ki bhinbhinahat (50 Hz), aur sur (F0) -> bhaari / halki.

  python tools/awaaz_bank.py ui                                  browser me form (record ya upload)
  python tools/awaaz_bank.py jaanch recording.wav                sirf jaanch
  python tools/awaaz_bank.py jodo गौरी saadharan rec.wav "jo bola wahi likho" --ling stri --umar jawan
  python tools/awaaz_bank.py dikhao                              bank me kaun-kaun
  python tools/awaaz_bank.py bolo गौरी "नमस्ते दादी" out.wav --bhaav khushi   (IndicF5 se)

Sab kuch aapke computer par: voices/bank/<kirdaar>/  +  knowledge/voice_bank.json
Kahani me: jo kirdaar bank me hai, cast_build/kahani_dimaag khud uski asli awaaz (engine "indicf5") lete hain;
line ka bhaav jis recording se mile (gussa -> gussa wali), wahi reference chuna jaata hai.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal as ss

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
BANK = ROOT / "voices" / "bank"
INDEX = ROOT / "knowledge" / "voice_bank.json"
SR = 24000            # IndicF5 24 kHz par kaam karta hai

# bhaav -> (naam, padhne ka vaakya, zaroori?)   naam kahani_rules.json ke bhaav se mel khaate hain
SLOTS = {
    "saadharan": ("Saadharan (zaroori)",
                  "आज सुबह मैं बाज़ार गया और ताज़ी सब्ज़ियाँ, फल और थोड़ी मिठाई ले आया। "
                  "क्या तुम्हें पता है, नदी के उस पार एक पुराना मंदिर है?", True),
    "khushi":   ("Khushi / hansna", "अरे वाह! हा हा हा... सच में? ये तो कमाल हो गया!", False),
    "gussa":    ("Gussa", "बस! बहुत हो गया। मैंने कितनी बार कहा है, ये काम मत करो!", False),
    "udaas":    ("Udaas", "अब वो दिन कभी वापस नहीं आएँगे... मुझे उसकी बहुत याद आती है।", False),
    "dar":      ("Dar", "कौन है वहाँ? मुझे... मुझे बहुत डर लग रहा है।", False),
    "dheere":   ("Dheere / fusfusana", "श्श्श... धीरे बोलो, कोई सुन लेगा।", False),
    "chillana": ("Pukaar / chillana", "अरे ओ मोहन! जल्दी इधर आओ!", False),
    "pyaar":    ("Pyaar / dulaar", "आ जा बेटा, मेरे पास बैठ। सब ठीक हो जाएगा।", False),
}
LING = ["stri", "purush", "bachcha", "budha", "budhi"]
UMAR = ["bachcha (5-12)", "kishor (13-19)", "jawan (20-40)", "madhyam (40-60)", "budha (60+)"]
# jo bhaav na ho to kiske sabse kareeb
NEAREST = {"hairani": "khushi", "thakan": "udaas", "chillana": "gussa", "dheere": "saadharan", "pyaar": "saadharan"}


# ============================================================================ jaanch
def _load(path, sr=SR):
    y, r = sf.read(str(path), always_2d=True)
    y = y.mean(axis=1).astype(np.float64)
    if r != sr:
        from math import gcd
        g = gcd(int(r), sr); y = ss.resample_poly(y, sr // g, int(r) // g)
    return y


def jaanch(path) -> dict:
    """Recording ki jaanch. Lautata hai naap + 'theek' + saaf salah (Hinglish)."""
    try:
        y = _load(path)
    except Exception as e:
        return {"theek": False, "salah": [f"File khul nahi rahi ({type(e).__name__}). WAV/MP3/M4A do."], "naap": {}}
    dur = len(y) / SR
    clip = float(np.mean(np.abs(y) > 0.985))
    peak = float(np.max(np.abs(y)) + 1e-12)
    n = int(0.02 * SR)
    e = np.maximum(np.array([np.sqrt(np.mean(y[i:i + n] ** 2)) for i in range(0, max(1, len(y) - n), n)]), 3e-5)
    thr = 0.12 * np.percentile(e, 95)
    speech = float(np.mean(e > thr))
    snr = float(20 * np.log10(np.percentile(e, 90) / np.percentile(e, 8)))
    quiet = np.repeat(e <= np.percentile(e, 15), n)[:len(y)]            # sabse shaant 15% hissa = chupp
    hum = -99.0
    if quiet.sum() > SR * 0.2:                     # chupp wale hisse me 50/100 Hz bhinbhinahat (pankha/bijli)
        q = y[:len(quiet)][quiet]
        if np.sqrt(np.mean(q ** 2)) > 3e-4:      # bilkul khaali (digital chupp) me bhinbhin nahi hoti
            f, p = ss.welch(q, SR, nperseg=4096)
            band = lambda a, b: p[(f >= a) & (f <= b)].sum()
            hum = float(10 * np.log10((band(45, 55) + band(95, 105) + 1e-15) / (band(20, 4000) + 1e-15)))
        else:
            hum = -99.0
    # goonj ka andaza: bolna rukne ke baad awaaz kitni der me 25 dB girti hai
    ends, tail = np.flatnonzero((e[:-1] > thr * 3) & (e[1:] <= thr * 3)), []
    for i in ends:
        seg = 20 * np.log10(e[i:i + 40] / e[i])
        k = np.flatnonzero(seg < -25)
        if len(k): tail.append(k[0] * 0.02)
    goonj = float(np.median(tail)) if tail else 0.0
    f0 = 0.0
    try:
        import parselmouth
        pt = parselmouth.Sound(y, SR).to_pitch(pitch_floor=70, pitch_ceiling=600)
        fr = pt.selected_array["frequency"]; fr = fr[fr > 0]
        f0 = float(np.median(fr)) if len(fr) else 0.0
    except Exception:
        pass
    naap = {"lambai_s": round(dur, 1), "bolna_%": int(speech * 100), "shor_snr_db": round(snr, 1),
            "phata_%": round(clip * 100, 2), "peak": round(peak, 2), "bhinbhin_db": round(hum, 1),
            "goonj_s": round(goonj, 2), "sur_hz": round(f0)}
    s = []
    if dur < 5: s.append("Bahut chhoti — 6 se 12 second bolo.")
    if dur > 20: s.append("Bahut lambi — 6 se 12 second kaafi hai (lambi clip se clone bigadta hai).")
    if speech < 0.45: s.append("Chupp zyada hai — lagataar bolo, shuru/ant ki khaali jagah kam.")
    if snr < 25: s.append("Peeche shor hai — pankha/AC/TV band karo, shaant kamra lo.")
    if clip > 0.001 or peak > 0.99: s.append("Awaaz phat rahi hai — phone thoda door (15-20 cm) ya dheema bolo.")
    if peak < 0.12: s.append("Awaaz bahut dheemi — phone thoda paas ya thoda zor se.")
    if hum > -12: s.append("Bijli/pankhe ki bhinbhin hai — charger nikaalo, pankha band.")
    if goonj > 0.35: s.append("Goonj (echo) hai — chhota kamra, parde/bistar wala; bathroom/khaali kamra nahi.")
    if f0 == 0: s.append("Insaan ki awaaz pakad nahi aayi — dobara record karo.")
    return {"theek": not s, "salah": s or ["Badhiya recording ✓"], "naap": naap}


def group(ling, f0):
    """Bhaari / halki — apne ling ke saamaanya sur ke hisaab se."""
    base = {"stri": 210, "budhi": 190, "purush": 120, "budha": 115, "bachcha": 280}.get(ling, 160)
    if not f0: return "?"
    r = f0 / base
    return "bhaari" if r < 0.9 else ("halki" if r > 1.1 else "beech")


# ============================================================================ bank
def _index():
    import astra_paths as _AP
    return _AP.read_json(INDEX, apni=True)


def _save_index(ix):
    INDEX.parent.mkdir(exist_ok=True)
    INDEX.write_text(json.dumps(ix, ensure_ascii=False, indent=1), encoding="utf-8")


def _clean(y):
    """Shuru/ant ki chupp kaato, 80 Hz se neeche ki gadgadahat hatao, -20 dBFS RMS."""
    y = ss.sosfilt(ss.butter(4, 80 / (SR / 2), btype="high", output="sos"), y)
    n = int(0.02 * SR)
    e = np.array([np.sqrt(np.mean(y[i:i + n] ** 2)) for i in range(0, max(1, len(y) - n), n)])
    on = np.flatnonzero(e > 0.1 * np.percentile(e, 95))
    if len(on):
        y = y[max(0, on[0] * n - int(0.15 * SR)): min(len(y), (on[-1] + 1) * n + int(0.25 * SR))]
    y = y / (np.sqrt(np.mean(y ** 2)) + 1e-9) * 0.1
    return np.clip(y, -0.98, 0.98)


def jodo(kirdaar, bhaav, path, text, ling="stri", umar="", ijazat=False, force=False):
    if bhaav not in SLOTS:
        raise SystemExit(f"bhaav inme se ho: {', '.join(SLOTS)}")
    if not ijazat:
        raise SystemExit("Jiski awaaz hai uski ijazat chahiye (bachche ke liye maa-baap ki). --ijazat lagao.")
    if not text.strip():
        raise SystemExit("Recording me jo bola, wahi shabd-ba-shabd likho — iske bina clone bigadta hai.")
    j = jaanch(path)
    if not j["theek"] and not force:
        return {"saved": False, **j}
    d = BANK / kirdaar; d.mkdir(parents=True, exist_ok=True)
    sf.write(str(d / f"{bhaav}.wav"), _clean(_load(path)).astype("float32"), SR, subtype="PCM_16")
    (d / f"{bhaav}.txt").write_text(text.strip(), encoding="utf-8")
    ix = _index()
    ent = ix.setdefault(kirdaar, {"ling": ling, "umar": umar, "bhaav": {}, "ijazat": time.strftime("%Y-%m-%d")})
    ent["ling"] = ling or ent["ling"]; ent["umar"] = umar or ent.get("umar", "")
    ent["bhaav"][bhaav] = {"wav": str((d / f"{bhaav}.wav").relative_to(ROOT)), "text": text.strip(), **j["naap"]}
    if bhaav == "saadharan":
        ent["sur_hz"] = j["naap"]["sur_hz"]; ent["rang"] = group(ent["ling"], j["naap"]["sur_hz"])
    _save_index(ix)
    return {"saved": True, **j}


def reference_for(kirdaar, bhaav=()):
    """Line ke bhaav ke hisaab se sabse sahi recording: (wav path, uska text, kaun sa bhaav mila)."""
    ent = _index().get(kirdaar)
    if not ent:
        raise KeyError(f"{kirdaar} awaaz-bank me nahi")
    have = ent["bhaav"]
    for b in list(bhaav) + [NEAREST.get(b) for b in bhaav] + ["saadharan"]:
        if b and b in have:
            return ROOT / have[b]["wav"], have[b]["text"], b
    b = next(iter(have))
    return ROOT / have[b]["wav"], have[b]["text"], b


def dikhao():
    ix = _index()
    if not ix:
        print("Bank khaali hai. python tools/awaaz_bank.py ui"); return
    for k, v in ix.items():
        print(f"{k:<12} {v['ling']:<8} {v.get('umar',''):<16} sur {v.get('sur_hz','?'):>4} Hz  {v.get('rang','?'):<7}"
              f" bhaav: {', '.join(v['bhaav'])}")


# ============================================================================ IndicF5 (model ek hi baar load)
_ENG = None


class IndicF5Engine:
    """indicf5_fix_v1/indicf5_render.py ka build_model — par model/vocoder ek baar, har line ke liye nahi."""
    def __init__(self, device=None):
        import importlib.util
        p = ROOT / "indicf5_fix_v1" / "indicf5_render.py"
        spec = importlib.util.spec_from_file_location("indicf5_render", p)
        self.R = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.R)
        if device is None:
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else ("mps" if getattr(torch.backends, "mps", None)
                                                                   and torch.backends.mps.is_available() else "cpu")
            except Exception:
                device = "cpu"
        self.device = device
        from f5_tts.infer.utils_infer import load_vocoder, preprocess_ref_audio_text, infer_process
        self._prep, self._infer = preprocess_ref_audio_text, infer_process
        print(f"[awaaz_bank] IndicF5 load ho raha hai ({device}) — pehli baar thoda samay lagega", file=sys.stderr)
        self.model = self.R.build_model(device, self.R._token(), None)
        self.vocoder = load_vocoder("vocos", is_local=False, device=device)
        self._refs = {}

    def say(self, text, ref_wav, ref_text, out):
        key = str(ref_wav)
        if key not in self._refs:
            self._refs[key] = self._prep(str(ref_wav), ref_text, show_info=lambda *a, **k: None)
        rw, rt = self._refs[key]
        res = self._infer(rw, rt, text, self.model, self.vocoder, show_info=lambda *a, **k: None)
        wav, sr = res[0], int(res[1])
        if wav is None or len(wav) == 0:
            raise RuntimeError("IndicF5 ne khaali awaaz di")
        sf.write(str(out), np.asarray(wav, dtype="float32"), sr, subtype="PCM_16")
        return out


_ENG_ERR = None


def engine():
    """Ek hi baar load. Fail hua to yaad rakho — har line par dobara koshish (aur dheemapan) nahi."""
    global _ENG, _ENG_ERR
    if _ENG_ERR is not None:
        raise RuntimeError(_ENG_ERR)
    if _ENG is None:
        try:
            _ENG = IndicF5Engine(os.environ.get("ASTRA_F5_DEVICE") or None)
        except Exception as e:
            _ENG_ERR = f"IndicF5 load nahi hua: {type(e).__name__}: {str(e)[:160]} (indicf5_fix_v1/INSTALL_HI.md)"
            raise RuntimeError(_ENG_ERR)
    return _ENG


def cast_entries():
    """cast_build ke liye: bank ka har kirdaar = engine 'indicf5' (sur/raftaar asli, koi badlav nahi)."""
    return {k: dict(engine="indicf5", bank=k, pitch=1.0, tempo=1.0, tilt=0.0, breath=0.0, vib=0.0,
                    form="preserved", ling=v.get("ling"), rang=v.get("rang"))
            for k, v in _index().items()}


# ============================================================================ form (browser)
def ui(port=7861):
    import gradio as gr
    with gr.Blocks(title="ASTRA Awaaz Bank") as app:
        gr.Markdown("## 🎙️ ASTRA Awaaz Bank\nHar kirdaar ki asli awaaz. **Saadharan zaroori**, baaki bhaav jitne chaho. "
                    "Shaant kamra · phone 15-20 cm · 6-12 second · jo bola wahi likho · WhatsApp wali file nahi.")
        with gr.Row():
            naam = gr.Textbox(label="Kirdaar ka naam (jaise गौरी, दादी, बच्चा-1)")
            ling = gr.Dropdown(LING, value="stri", label="Ling / kism")
            umar = gr.Dropdown(UMAR, value=UMAR[2], label="Umar")
        ijazat = gr.Checkbox(label="Jiski awaaz hai unki ijazat li hai (bachche ke liye maa-baap ki)")
        inputs = []
        for b, (label, line, req) in SLOTS.items():
            with gr.Accordion(("⭐ " if req else "") + label, open=req):
                gr.Markdown(f"**Ye padho:** {line}")
                a = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Record karo ya file daalo")
                t = gr.Textbox(value=line, label="Jo bola wahi (badla ho to yahan theek karo)")
                inputs += [a, t]
        with gr.Row():
            b_check = gr.Button("1. Jaanch karo")
            b_save = gr.Button("2. Bank me save karo", variant="primary")
        force = gr.Checkbox(label="Kuch kami ho phir bhi save karo (sujhaav nahi)")
        result = gr.Markdown()
        bank = gr.Markdown(value=lambda: _bank_md())

        def _rows(vals, save, n, l, u, ij, fc):
            rows, keys = [], list(SLOTS)
            for i, b in enumerate(keys):
                a, t = vals[2 * i], vals[2 * i + 1]
                if not a:
                    if SLOTS[b][2]: rows.append(f"❌ **{SLOTS[b][0]}** — ye zaroori hai, record karo")
                    continue
                if save:
                    if not n.strip(): return "❌ Kirdaar ka naam likho"
                    if not ij: return "❌ Ijazat wala box tick karo"
                    r = jodo(n.strip(), b, a, t, l, u, True, fc)
                    mark = "✅ save" if r["saved"] else "⚠️ save NAHI hua"
                else:
                    r = jaanch(a); mark = "✅" if r["theek"] else "⚠️"
                nm = r["naap"]
                rows.append(f"{mark} **{SLOTS[b][0]}** — {' · '.join(r['salah'])}  \n"
                            f"<small>lambai {nm.get('lambai_s')}s · shor {nm.get('shor_snr_db')} dB · "
                            f"sur {nm.get('sur_hz')} Hz · goonj {nm.get('goonj_s')}s</small>")
            if save and n.strip() and n.strip() in _index():
                e = _index()[n.strip()]
                rows.append(f"\n**{n}**: {e['ling']}, sur {e.get('sur_hz','?')} Hz → **{e.get('rang','?')}** awaaz")
            return "\n\n".join(rows) or "Kuch record nahi kiya"

        b_check.click(lambda *v: _rows(v[:-5], False, *v[-5:]), inputs + [naam, ling, umar, ijazat, force], result)
        b_save.click(lambda *v: _rows(v[:-5], True, *v[-5:]), inputs + [naam, ling, umar, ijazat, force], result) \
              .then(_bank_md, None, bank)
    app.launch(server_name="127.0.0.1", server_port=port)     # sirf aapke computer par, internet par nahi


def _bank_md():
    ix = _index()
    if not ix: return "**Bank:** abhi khaali"
    return "**Bank:**  \n" + "  \n".join(f"• {k} — {v['ling']}, {v.get('rang','?')} ({v.get('sur_hz','?')} Hz), "
                                       f"bhaav: {', '.join(v['bhaav'])}" for k, v in ix.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ui", "jaanch", "jodo", "dikhao", "bolo"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--ling", default="stri"); ap.add_argument("--umar", default="")
    ap.add_argument("--ijazat", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--bhaav", default=""); ap.add_argument("--port", type=int, default=7861)
    a = ap.parse_args()
    if a.cmd == "ui": ui(a.port); return 0
    if a.cmd == "dikhao": dikhao(); return 0
    if a.cmd == "jaanch":
        r = jaanch(a.args[0]); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["theek"] else 1
    if a.cmd == "jodo":
        k, b, p, t = a.args[:4]
        r = jodo(k, b, p, t, a.ling, a.umar, a.ijazat, a.force); print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["saved"] else 1
    if a.cmd == "bolo":
        k, text, out = a.args[:3]
        ref, rt, got = reference_for(k, [x for x in a.bhaav.split(",") if x])
        print(f"reference: {got}"); engine().say(text, ref, rt, out); print(out); return 0


if __name__ == "__main__":
    raise SystemExit(main())
