from pathlib import Path
import json, shutil, hashlib, datetime

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

class AssetWorkspace:
    def __init__(self, root):
        self.root=Path(root)
        for name in ("original","processed","reports"): (self.root/name).mkdir(parents=True,exist_ok=True)
        self.manifest_path=self.root/"manifest.json"
        if not self.manifest_path.exists():
            self.manifest_path.write_text(json.dumps({"schema":"astra-audio-library/v1","assets":[]},indent=2),encoding="utf-8")

    def register(self, source, processed=None, report=None, tags=()):
        source=Path(source)
        digest=sha256_file(source)
        original=self.root/"original"/(digest[:12]+"_"+source.name)
        if not original.exists(): shutil.copy2(source,original)
        record={
            "asset_id":digest[:16], "source_name":source.name,
            "sha256":digest, "original_copy":str(original),
            "processed_file":str(processed) if processed else None,
            "report_file":str(report) if report else None,
            "tags":list(tags),
            "registered_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "license_status":"unknown_requires_verification"
        }
        data=json.loads(self.manifest_path.read_text(encoding="utf-8"))
        data["assets"]=[a for a in data["assets"] if a["asset_id"]!=record["asset_id"]]+[record]
        self.manifest_path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        return record
