
"""Performance markup and dialogue planning.

Supported authoring syntax:
  आरव [भाव:खुश]: अरे वाह!
  [विराम:500ms]
  [खींचें:नहीं]  -> only the marked word is deliberately lengthened.

No automatic elongation is applied to ordinary words.
"""
import re

EMOTION_MAP = {
    "खुश":"happy", "प्रसन्न":"happy", "उदास":"sad", "दुखी":"sad",
    "गुस्सा":"angry", "क्रोधित":"angry", "डरा":"fearful", "डर":"fearful",
    "हैरान":"surprised", "जिज्ञासु":"curious", "गंभीर":"serious",
    "फुसफुस":"whisper", "जोर से":"shout", "हँसी":"laughing", "रोना":"crying"
}
PAUSE_RE = re.compile(r"\[विराम:(\d{1,4})ms\]")
STRETCH_RE = re.compile(r"\[खींचें:([^\]]{1,40})\]")
EMOTION_RE = re.compile(r"\[भाव:([^\]]{1,20})\]")
SPEAKER_RE = re.compile(r"^\s*([^:：\[]+?)(?:\s*\[भाव:([^\]]+)\])?\s*[:：]\s*(.*)$")

def parse_performance_line(line):
    raw=line.strip()
    if not raw:
        return {"kind":"blank"}
    m=SPEAKER_RE.match(raw)
    speaker=None; emotion="neutral"; text=raw
    if m:
        speaker=m.group(1).strip()
        emotion=EMOTION_MAP.get((m.group(2) or "").strip(),"neutral")
        text=m.group(3).strip()
    events=[]
    pos=0
    for match in re.finditer(r"\[विराम:(\d{1,4})ms\]|\[खींचें:([^\]]{1,40})\]",text):
        if match.start()>pos:
            events.extend(_text_events(text[pos:match.start()],emotion))
        if match.group(1):
            events.append({"kind":"pause","duration_ms":min(2000,max(80,int(match.group(1))))})
        else:
            word=match.group(2).strip()
            if word:
                events.append({"kind":"text","text":word,"emotion":emotion,"stretch":True})
        pos=match.end()
    if pos<len(text):
        events.extend(_text_events(text[pos:],emotion))
    return {"kind":"dialogue" if speaker else "narration","speaker":speaker,"emotion":emotion,"events":events}

def _text_events(text, emotion):
    # Preserve punctuation in text. Punctuation pause is metadata only; no arbitrary word stretching.
    text=text.strip()
    if not text: return []
    events=[{"kind":"text","text":text,"emotion":emotion,"stretch":False}]
    tail=text[-1]
    pause={",":130,"，":130,";":180,"；":180,":":160,"।":340,".":300,"?":300,"!":300,"…":450}.get(tail)
    if pause:
        events.append({"kind":"pause","duration_ms":pause,"source":"punctuation"})
    return events

def plan_script(text):
    rows=[]
    for n,line in enumerate(text.replace("\r\n","\n").splitlines(),1):
        item=parse_performance_line(line)
        if item["kind"]!="blank":
            item["line"]=n; rows.append(item)
    return rows

def stretch_rate(base_rate, adapter):
    # Backend-specific speed control, applied only to explicitly marked text.
    if adapter=="edge":
        # Edge rate values are percentage strings, e.g. +0%.
        try: base=int(str(base_rate).replace("%","").replace("+",""))
        except Exception: base=0
        return f"{min(0,base-18):+d}%"
    if adapter=="espeak":
        return "slow"
    if adapter=="piper":
        return "slow"
    if adapter=="elevenlabs":
        return "slow"
    return "slow"
