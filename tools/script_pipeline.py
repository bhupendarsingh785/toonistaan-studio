#!/usr/bin/env python3
"""ASTRA script planner: Unicode-safe chunking and explicit speaker/emotion metadata.
No backend emotion control is implied by parsing these labels.
"""
from __future__ import annotations
import argparse, json, re, unicodedata
from pathlib import Path

EMOTIONS = {
    "neutral", "sad", "dukh", "pain", "khushi", "happy", "gussa", "anger",
    "dar", "fear", "pyaar", "love", "hasi", "hasai", "laugh", "cry", "rona",
    "whisper", "shout", "surprise", "ashcharya", "calm", "excited"
}
TAG = re.compile(r"\[([a-zA-Z_-]+)\]")
SPEAKER = re.compile(r"^\s*([^:\n]{1,48})\s*:\s*(.*)$")

def _strip_emotion(text: str) -> tuple[str, str]:
    found = [m for m in TAG.finditer(text) if m.group(1).lower() in EMOTIONS]
    if not found:
        return "neutral", text.strip()
    # First recognized tag controls the chunk; all recognized tags are removed from spoken text.
    emotion = found[0].group(1).lower()
    cleaned = TAG.sub(lambda m: "" if m.group(1).lower() in EMOTIONS else m.group(0), text)
    return emotion, cleaned.strip(" :—-\t")

def parse_script_line(raw: str, default_speaker: str = "default") -> dict | None:
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    # Support both '[sad] Grandma: text' and 'Grandma [sad]: text'.
    emotion, line = _strip_emotion(line)
    speaker = default_speaker
    m = SPEAKER.match(line)
    if m:
        speaker, line = m.group(1).strip(), m.group(2).strip()
        # Emotion tag may have been inside speaker prefix.
        emotion2, line2 = _strip_emotion(line)
        if emotion2 != "neutral": emotion = emotion2
        line = line2
    if not line:
        return None
    return {"speaker": speaker, "emotion": emotion, "text": line}

def _graphemes(text: str) -> list[str]:
    """Keep combining marks with their base code point when hard splitting Hindi words."""
    out=[]
    for ch in text:
        if out and (unicodedata.combining(ch) or ch in ("\u200d", "\ufe0f") or out[-1].endswith("\u200d")):
            out[-1] += ch
        else:
            out.append(ch)
    return out

def _hard_split_token(token: str, limit: int) -> list[str]:
    clusters = _graphemes(token)
    return ["".join(clusters[i:i+limit]) for i in range(0, len(clusters), limit)]

def _split_oversize(text: str, max_chars: int) -> list[str]:
    parts = re.split(r"(?<=[।.!?;:])\s+|(?<=,)\s+", text)
    chunks, current = [], ""
    for part in parts:
        if not part: continue
        if len(part) > max_chars:
            if current: chunks.append(current); current = ""
            words = part.split()
            buf = ""
            for word in words:
                if len(word) > max_chars:
                    if buf: chunks.append(buf); buf = ""
                    pieces = _hard_split_token(word, max_chars)
                    chunks.extend(pieces[:-1]); buf = pieces[-1]
                elif not buf or len(buf) + 1 + len(word) <= max_chars:
                    buf = (buf + " " + word).strip()
                else:
                    chunks.append(buf); buf = word
            if buf: chunks.append(buf)
        elif not current: current = part
        elif len(current) + 1 + len(part) <= max_chars: current += " " + part
        else: chunks.append(current); current = part
    if current: chunks.append(current)
    return chunks

def prepare_script(text: str, max_chars: int = 280, default_speaker: str = "default") -> list[dict]:
    if not isinstance(max_chars, int) or max_chars < 40:
        raise ValueError("max_chars kam se kam 40 hona chahiye")
    result=[]; seq=0
    for raw in text.splitlines():
        parsed=parse_script_line(raw, default_speaker)
        if not parsed: continue
        for chunk_no, chunk in enumerate(_split_oversize(parsed["text"], max_chars), 1):
            if not chunk.strip(): continue
            seq += 1
            result.append({"sequence":seq,"speaker":parsed["speaker"],"emotion":parsed["emotion"],"text":chunk,"chunk":chunk_no})
    return result

def prepare_file(source: str, output: str, max_chars: int = 280) -> dict:
    p=Path(source)
    if not p.is_file(): raise FileNotFoundError(source)
    items=prepare_script(p.read_text(encoding="utf-8-sig"),max_chars=max_chars)
    payload={"schema_version":2,"source":p.name,"max_chars":max_chars,"chunks":len(items),"items":items,
             "important_note":"Emotion labels are metadata only unless a selected backend explicitly supports and receives emotion conditioning."}
    out=Path(output); out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_name(out.name+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(out)
    return payload

def main() -> int:
    ap=argparse.ArgumentParser(description="ASTRA long-form script planner")
    ap.add_argument("--in",dest="src",required=True); ap.add_argument("--out",required=True); ap.add_argument("--max-chars",type=int,default=280)
    a=ap.parse_args()
    try:
        report=prepare_file(a.src,a.out,a.max_chars)
        print(json.dumps({k:report[k] for k in ("chunks","max_chars","source")},ensure_ascii=False)); return 0
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}"); return 1
if __name__=="__main__": raise SystemExit(main())
