#!/usr/bin/env python3
"""Sarvam Keys — 6 ID tak rotation (coin khatam ho to agla, dead key yaad rakho).

Kaam:
  1) 6 tak key padhta hai: SARVAM_API_KEY, _2 … _6
  2) Har key ka haal yaad rakhta hai (state file): ok / dead / cooldown
  3) Coin/quota khatam (401/402/403/429) -> us key ko **cooldown** me daal kar agla
  4) Server error (5xx) -> usi key se dobara, agla nahi (coin bachao)
  5) Chhoti si state file: .sarvam_keys_state.json (key kabhi nahi likhti — sirf hash)

CLI:
  python tools/sarvam_keys.py status          # kaunsi key zinda/dead (naam + hash)
  python tools/sarvam_keys.py reset           # sab cooldown saaf
"""
from __future__ import annotations
import hashlib, json, os, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".sarvam_keys_state.json"
NAMES = [f"SARVAM_API_KEY{'' if i == 1 else '_' + str(i)}" for i in range(1, 7)]
COOLDOWN_SECS = int(os.environ.get("SARVAM_KEY_COOLDOWN", "3600"))


def _hash(k: str) -> str:
    return hashlib.sha256(k.encode()).hexdigest()[:10]


def all_keys() -> list[tuple[str, str]]:
    """[(naam, key)] — sirf jo set hain (duplicate hata kar)."""
    out, seen = [], set()
    for name in NAMES:
        k = (os.environ.get(name) or "").strip().strip('"').strip("'")
        k = re.sub(r"[^A-Za-z0-9\-_]", "", k)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append((name, k))
    return out


def _load() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict) -> None:
    try:
        STATE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def order() -> list[tuple[str, str]]:
    """Zinda keys pehle, cooldown wali sabse aakhir (phir bhi try hoti hain)."""
    state = _load()
    now = time.time()
    keys = all_keys()
    alive, cooling = [], []
    for name, k in keys:
        row = state.get(_hash(k), {})
        until = float(row.get("cooldown_until", 0))
        (cooling if until > now else alive).append((name, k))
    return alive + cooling


def mark_ok(key: str) -> None:
    state = _load()
    h = _hash(key)
    state[h] = {"name": next((n for n, k in all_keys() if k == key), "?"),
                "status": "ok", "last_ok": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "uses": int(state.get(h, {}).get("uses", 0)) + 1}
    _save(state)


def mark_quota_dead(key: str, code: int) -> None:
    """Coin/quota khatam — is key ko cooldown me daalo (agli baar aakhir me try hogi)."""
    state = _load()
    h = _hash(key)
    row = state.get(h, {})
    row.update({"name": next((n for n, k in all_keys() if k == key), "?"),
                "status": f"quota_{code}",
                "cooldown_until": time.time() + COOLDOWN_SECS,
                "last_dead": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    state[h] = row
    _save(state)


def reset() -> dict:
    _save({})
    return {"reset": True, "file": str(STATE)}


def status() -> dict:
    state = _load()
    now = time.time()
    rows = []
    for name, k in all_keys():
        row = state.get(_hash(k), {})
        until = float(row.get("cooldown_until", 0))
        rows.append({"name": name, "hash": _hash(k),
                     "status": row.get("status", "naya"),
                     "uses": row.get("uses", 0),
                     "cooldown_min": round((until - now) / 60, 1) if until > now else 0})
    return {"keys": rows, "count": len(rows), "rotation_ready": len(rows) >= 2}


def main() -> int:
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    print(json.dumps(reset() if cmd == "reset" else status(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
