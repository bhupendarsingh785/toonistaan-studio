#!/usr/bin/env python3
"""
Toonistaan AI layer — bina key bhi chalta hai, key ho to behtar hota hai.

Order:
1. GEMINI_API_KEY      (Google AI Studio — free tier)
2. OPENROUTER_API_KEY  (free models, jaise meta-llama / mistral)
3. HF_TOKEN            (Hugging Face Inference — free)
4. GROQ_API_KEY        (free tier, tez)
5. kuch nahi           -> None (caller apna local/pollinations tareeka use karega)

Sirf text ke liye. Tasveer Pollinations se banti hai (bina key).
"""
import json
import os
import urllib.request

TIMEOUT = 60


def _post(url, headers, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def _gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.0-flash:generateContent?key=" + key)
    d = _post(url, {"Content-Type": "application/json"},
              {"contents": [{"parts": [{"text": prompt}]}]})
    return d["candidates"][0]["content"]["parts"][0]["text"]


def _openrouter(prompt):
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    d = _post("https://openrouter.ai/api/v1/chat/completions",
              {"Content-Type": "application/json", "Authorization": "Bearer " + key},
              {"model": os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
               "messages": [{"role": "user", "content": prompt}]})
    return d["choices"][0]["message"]["content"]


def _groq(prompt):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    d = _post("https://api.groq.com/openai/v1/chat/completions",
              {"Content-Type": "application/json", "Authorization": "Bearer " + key},
              {"model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
               "messages": [{"role": "user", "content": prompt}]})
    return d["choices"][0]["message"]["content"]


def _hf(prompt):
    key = os.environ.get("HF_TOKEN", "").strip()
    if not key:
        return None
    d = _post("https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta",
              {"Content-Type": "application/json", "Authorization": "Bearer " + key},
              {"inputs": prompt, "parameters": {"max_new_tokens": 400}})
    if isinstance(d, list) and d and "generated_text" in d[0]:
        return d[0]["generated_text"]
    return None


PROVIDERS = [("gemini", _gemini), ("openrouter", _openrouter), ("groq", _groq), ("hf", _hf)]


def have_any_key():
    return any(os.environ.get(k, "").strip() for k in
               ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "HF_TOKEN"))


def ask(prompt, verbose=True):
    """Pehla provider jo jawab de. Koi key nahi / sab fail -> None."""
    for name, fn in PROVIDERS:
        try:
            out = fn(prompt)
            if out and str(out).strip():
                if verbose:
                    print("AI_PROVIDER", name, flush=True)
                return str(out).strip()
        except Exception as e:
            if verbose:
                print("AI_FAIL", name, str(e)[:70], flush=True)
    if verbose:
        print("AI_NONE (koi key nahi ya sab fail) — local tareeka chalega", flush=True)
    return None


def enhance_image_prompt(scene_text, style="", cast=""):
    """Scene ki line ko behtar English image prompt me badlo. Key na ho to None."""
    p = (
        "You write image prompts for a 3D animated Indian cartoon movie. "
        "Reply with ONE line only, in English, max 40 words, no quotes.\n"
        f"Characters: {cast or 'the same characters in every scene'}\n"
        f"Style: {style or 'Pixar-like 3D animation, cinematic light'}\n"
        f"Scene: {scene_text}\n"
        "Prompt:"
    )
    out = ask(p, verbose=True)
    if not out:
        return None
    out = out.strip().split("\n")[0].strip().strip('"').strip()
    return out[:400] or None


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "Say hello in one short line"
    print(ask(q) or "(koi key nahi — bina key chal raha hai)")
