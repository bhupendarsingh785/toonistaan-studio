"""Server se aayi files kholo: ample_server_exec output mein `@@naam` + base64 lines.
python unpack_exec.py <saved_tool_result.txt> <out_dir>"""
import json, base64, re, sys, os
t = open(sys.argv[1], encoding="utf-8").read()
try:
    s = json.loads(t)["stdout"]
except Exception:
    s = t
out = sys.argv[2]; os.makedirs(out, exist_ok=True)
for m in re.finditer(r"@@(\S+)\n([A-Za-z0-9+/=]+)", s):
    p = os.path.join(out, m.group(1)); open(p, "wb").write(base64.b64decode(m.group(2))); print(p)
tail = re.sub(r"@@\S+\n[A-Za-z0-9+/=]+\n?", "", s).strip()
if tail: print("--- other output ---\n" + tail[-2000:])
