
"""Persistent per-engine error ledger with regression-test references."""
import json, hashlib, time
from pathlib import Path
class ErrorLedger:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists(): self.path.write_text("[]", encoding="utf-8")
    def _read(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception: return []
    def add(self, title, symptom, root_cause, fix, prevention, regression_test, severity="medium"):
        fingerprint = hashlib.sha256((title+"|"+symptom).encode()).hexdigest()[:16]
        rows = self._read()
        # purane ledger rows me "fingerprint" nahi hota — seedha x["fingerprint"] crash karta tha
        existing = next((x for x in rows if x.get("fingerprint") == fingerprint), None)
        if existing:
            existing["repeat_observations"] = int(existing.get("repeat_observations", 1)) + 1
            existing["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            existing["status"] = "REOPENED"
            existing["note"] = "Known issue reappeared; block release until regression test passes."
        else:
            rows.append({
                "fingerprint": fingerprint, "title": title, "symptom": symptom,
                "root_cause": root_cause, "fix": fix, "prevention": prevention,
                "regression_test": regression_test, "severity": severity,
                "status": "OPEN", "repeat_observations": 1,
                "first_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "last_seen": None
            })
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return fingerprint
    def close(self, fingerprint, evidence):
        rows = self._read()
        for x in rows:
            if x.get("fingerprint") == fingerprint:
                x["status"] = "FIXED_TESTED"
                x["fix_evidence"] = evidence
                x["closed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    def release_blockers(self):
        return [x for x in self._read() if x["status"] not in ("FIXED_TESTED",)]
