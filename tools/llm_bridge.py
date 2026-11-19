#!/usr/bin/env python3
"""ASTRA LLM Bridge — kisi bhi model se judne ka ek hi darwaza.

Kaam: OpenAI-compatible API wale kisi bhi provider (GPT, Groq, OpenRouter,
Together, local Ollama, ya apna server) se baat karna — bina SDK, sirf HTTP.
Ek key na ho to agla provider apne aap. Sab kuch report me likha jata hai.

Commands:
  python tools/llm_bridge.py status
  python tools/llm_bridge.py models
  python tools/llm_bridge.py chat "Hindi me do line likho"
  python tools/llm_bridge.py ask-file sawal.txt --out jawab.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"

# provider -> (base_url, env var, default model)
PROVIDERS: dict[str, dict] = {
    "openai":     {"base": "https://api.openai.com/v1",        "env": "OPENAI_API_KEY",     "model": "gpt-4o-mini"},
    "groq":       {"base": "https://api.groq.com/openai/v1",   "env": "GROQ_API_KEY",       "model": "llama-3.3-70b-versatile"},
    "openrouter": {"base": "https://openrouter.ai/api/v1",     "env": "OPENROUTER_API_KEY", "model": "openai/gpt-4o-mini"},
    "together":   {"base": "https://api.together.xyz/v1",      "env": "TOGETHER_API_KEY",   "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    "ollama":     {"base": "http://127.0.0.1:11434/v1",        "env": None,                 "model": "llama3.1"},
    "custom":     {"base": os.environ.get("LLM_BASE_URL", ""), "env": "LLM_API_KEY",        "model": os.environ.get("LLM_MODEL", "")},
}
ORDER = ["openai", "groq", "openrouter", "together", "ollama", "custom"]


@dataclass
class ProviderState:
    name: str
    ready: bool
    reason: str
    model: str = ""


def _key(env: str | None) -> str | None:
    if not env:
        return None
    v = os.environ.get(env, "").strip()
    return v or None


def status() -> list[ProviderState]:
    out = []
    for name in ORDER:
        spec = PROVIDERS[name]
        base = spec["base"]
        if not base:
            out.append(ProviderState(name, False, "base URL set nahi (LLM_BASE_URL)", spec["model"]))
            continue
        if spec["env"] and not _key(spec["env"]):
            out.append(ProviderState(name, False, f"{spec['env']} nahi mila", spec["model"]))
            continue
        out.append(ProviderState(name, True, "tayyar", spec["model"]))
    return out


def ready_providers() -> list[str]:
    return [s.name for s in status() if s.ready]


def _post(url: str, payload: dict, key: str | None, timeout: int = 90) -> dict:
    import requests
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:180]}")
    return r.json()


def chat(messages: list[dict], provider: str | None = None, model: str | None = None,
         temperature: float = 0.6, timeout: int = 90) -> tuple[str, dict]:
    """Ek jawab lo. Chain: diya hua provider, phir baaki tayyar log."""
    chain = ([provider] if provider else []) + [p for p in ready_providers() if p != provider]
    if not chain:
        raise RuntimeError("koi provider tayyar nahi — key ya base URL do")
    log = []
    for name in chain:
        spec = PROVIDERS.get(name)
        if not spec or not spec["base"]:
            log.append({"provider": name, "ok": False, "note": "base URL nahi"})
            continue
        use_model = model or spec["model"]
        if not use_model:
            log.append({"provider": name, "ok": False, "note": "model nahi"})
            continue
        try:
            data = _post(f"{spec['base'].rstrip('/')}/chat/completions",
                         {"model": use_model, "messages": messages, "temperature": temperature},
                         _key(spec["env"]), timeout)
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text.strip():
                log.append({"provider": name, "ok": True, "note": use_model})
                return text, {"provider": name, "model": use_model, "tries": log}
            log.append({"provider": name, "ok": False, "note": "khaali jawab"})
        except Exception as exc:
            log.append({"provider": name, "ok": False, "note": f"{type(exc).__name__}: {str(exc)[:140]}"})
    raise RuntimeError("sab provider fail: " + json.dumps(log, ensure_ascii=False))


def remember(question: str, answer: str, provider: str = "") -> Path:
    """Jo seekha use knowledge file me likho (taaki agli baar yaad rahe)."""
    KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    path = KNOWLEDGE / "seekha-hua.md"
    stamp = time.strftime("%Y-%m-%d %H:%M")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"\n## {stamp} · {provider or 'llm'}\n**Sawaal:** {question.strip()[:400]}\n\n"
                 f"**Jawab:** {answer.strip()[:1500]}\n")
    return path


def cmd_status() -> int:
    states = status()
    for s in states:
        print(f"{'[READY]' if s.ready else '[ --  ]'} {s.name:11s} {s.reason:34s} {s.model}")
    ready = [s.name for s in states if s.ready]
    print(f"\nChain: {' -> '.join(ORDER)}")
    print(f"Abhi chalenge: {', '.join(ready) if ready else 'koi nahi (key do)'}")
    return 0 if ready else 1


def cmd_chat(text: str, provider: str | None, remember_it: bool) -> int:
    msgs = [{"role": "system", "content": "Tum ASTRA ke sahayak ho. Hindi/Hinglish me seedha, saaf jawab do."},
            {"role": "user", "content": text}]
    try:
        answer, meta = chat(msgs, provider=provider)
    except Exception as exc:
        print(f"[x] {exc}")
        return 1
    print(answer)
    print(f"\n— {meta['provider']} / {meta['model']}")
    if remember_it:
        p = remember(text, answer, meta["provider"])
        print(f"[memory] {p.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ASTRA LLM bridge (koi bhi model)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("models")
    c = sub.add_parser("chat"); c.add_argument("text"); c.add_argument("--provider"); c.add_argument("--remember", action="store_true")
    f = sub.add_parser("ask-file"); f.add_argument("path"); f.add_argument("--provider"); f.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "models":
        print(json.dumps({k: v["model"] for k, v in PROVIDERS.items()}, ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "chat":
        return cmd_chat(a.text, a.provider, a.remember)
    text = Path(a.path).read_text(encoding="utf-8")
    try:
        answer, meta = chat([{"role": "user", "content": text}], provider=a.provider)
    except Exception as exc:
        print(f"[x] {exc}")
        return 1
    if a.out:
        Path(a.out).write_text(answer, encoding="utf-8")
        print(f"likh diya: {a.out}")
    else:
        print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
