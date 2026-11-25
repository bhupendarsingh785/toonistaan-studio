"""astra_paths.py — poore system ke raaste EK jagah (pehle 49 file me '/scratch/...' pakka likha tha).

  WORK    kaam/cache      ASTRA_WORK    warna /scratch/work (agar hai)  warna <ASTRA>/.work
  INPUT   aapki files     ASTRA_INPUT   warna /scratch/input (agar hai) warna <ASTRA>/input
  OUTPUT  bani cheezein   ASTRA_OUTPUT  warna /scratch/output (agar hai) warna <ASTRA>/out
  VOICES  Piper model     ASTRA_VOICES  warna <ASTRA>/voices (cast_build yahin download karta hai)
"""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pick(env, legacy, local):
    if os.environ.get(env):
        return Path(os.environ[env])
    if Path(legacy).is_dir():
        return Path(legacy)
    return local


WORK = _pick("ASTRA_WORK", "/scratch/work", ROOT / ".work")
INPUT = _pick("ASTRA_INPUT", "/scratch/input", ROOT / "input")
OUTPUT = _pick("ASTRA_OUTPUT", "/scratch/output", ROOT / "out")
VOICES = Path(os.environ["ASTRA_VOICES"]) if os.environ.get("ASTRA_VOICES") else (
    Path("/scratch/work/voices") if any(Path("/scratch/work/voices").glob("*.onnx")) else ROOT / "voices")

for _d in (WORK, INPUT, OUTPUT, VOICES):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def read_json(path, default=None, apni=False):
    """JSON padho bina system giraaye.
    apni=True  (aapki haath se likhi file: rules, voice_bank) -> galti ki line/column bata kar ruko.
    apni=False (system ki apni file: cast_auto, khoj_yaad)   -> kharab copy alag rakh kar naye sire se."""
    import json, time
    p = Path(path)
    if not p.exists():
        return {} if default is None else default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        if apni:
            raise SystemExit(f"{p.name} me likhne ki galti: line {e.lineno}, column {e.colno} — "
                             f"wahan comma , ya quote \" ya bracket dekho. ({e.msg})")
        bak = p.with_name(p.name + f".kharab-{time.strftime('%Y%m%d-%H%M%S')}")
        p.rename(bak)
        print(f"[astra] {p.name} kharab thi -> {bak.name} me rakh di, naye sire se shuru", flush=True)
        return {} if default is None else default
