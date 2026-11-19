
"""Local model inventory and conservative capability reporting."""
from pathlib import Path
import json, hashlib

MODEL_SUFFIXES = {".onnx", ".pt", ".pth", ".bin", ".safetensors", ".gguf", ".tflite", ".pb"}
def inspect_model_file(path):
    p = Path(path)
    if not p.is_file() or p.suffix.lower() not in MODEL_SUFFIXES:
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return {
        "name": p.name, "path": str(p.resolve()), "format": p.suffix.lower()[1:],
        "size_bytes": p.stat().st_size, "sha256": h.hexdigest(),
        "capabilities": ["unknown_until_model_card_or_manifest_verified"],
        "verified": False,
        "warning": "केवल फाइल मिलने से मॉडल की भाषा, गुणवत्ता या voice-design क्षमता प्रमाणित नहीं होती।"
    }

def scan_model_directories(paths):
    found = []
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
            continue
        candidates = [p] if p.is_file() else p.rglob("*")
        for item in candidates:
            record = inspect_model_file(item)
            if record:
                found.append(record)
    return found

def verify_manifest(manifest_path):
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    required = {"name", "version", "task", "languages", "license", "files"}
    missing = sorted(required - set(data))
    return {"valid_schema": not missing, "missing_fields": missing, "manifest": data}
