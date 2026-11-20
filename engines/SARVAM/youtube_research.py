"""Engine-local YouTube research: public metadata/captions only; never downloads video/audio."""
from __future__ import annotations
import hashlib, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests
try:
    from browser_agent_v08 import discover
except ModuleNotFoundError:
    from .browser_agent_v08 import discover

ENGINE = Path(__file__).resolve().parent.name.lower()
UA = "ASTRA-Independent-Research-Agent/1.0 (public metadata and captions only)"

def video_id(url: str) -> str | None:
    try:
        p=urlparse(url)
        host=(p.hostname or "").lower()
        if host in ("youtu.be","www.youtu.be"):
            value=p.path.strip("/").split("/")[0]
        elif host.endswith("youtube.com"):
            if p.path == "/watch": value=parse_qs(p.query).get("v",[""])[0]
            elif p.path.startswith(("/shorts/","/embed/","/live/")): value=p.path.split("/")[2]
            else: return None
        else: return None
        return value if re.fullmatch(r"[A-Za-z0-9_-]{11}",value or "") else None
    except Exception:
        return None

def _captions(vid: str, languages: list[str]):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None, "youtube-transcript-api is not installed"
    try:
        api=YouTubeTranscriptApi()
        fetched=api.fetch(vid,languages=languages)
        snippets=[]
        for item in fetched:
            if isinstance(item,dict):
                text=item.get("text",""); start=item.get("start",0); duration=item.get("duration",0)
            else:
                text=getattr(item,"text",""); start=getattr(item,"start",0); duration=getattr(item,"duration",0)
            if text:
                snippets.append({"start":float(start),"duration":float(duration),"text":str(text)})
        if not snippets:
            return None,"No public captions returned"
        lang=getattr(fetched,"language_code","unknown")
        generated=getattr(fetched,"is_generated",None)
        return {"language":lang,"is_generated":generated,"snippets":snippets},None
    except Exception as exc:
        return None,f"{type(exc).__name__}: {exc}"

def research_youtube(query: str, engine_root: Path | str, limit: int=5,
                     languages: tuple[str,...]=("hi","en","en-IN")) -> dict:
    if not isinstance(query,str) or not query.strip():
        raise ValueError("query cannot be empty")
    limit=max(1,min(int(limit),10))
    root=Path(engine_root).resolve()
    research_dir=root/"research"/"youtube"
    inbox_dir=root/"knowledge_inbox"/"youtube"
    research_dir.mkdir(parents=True,exist_ok=True)
    inbox_dir.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    session.headers.update({"User-Agent":UA})
    candidates=[]; errors=[]
    for q in (f"site:youtube.com/watch {query}", f"site:youtu.be {query}"):
        try:
            rows,errs=discover(q,session,limit=limit*4)
            errors.extend(errs[:5])
            for url,title,provider in rows:
                vid=video_id(url)
                if vid and all(x["video_id"]!=vid for x in candidates):
                    candidates.append({"video_id":vid,"url":f"https://www.youtube.com/watch?v={vid}",
                                       "title":title or "YouTube video","discovery_provider":provider})
                if len(candidates)>=limit: break
        except Exception as exc:
            errors.append({"provider":"youtube_discovery","error":f"{type(exc).__name__}: {exc}"})
        if len(candidates)>=limit: break
    results=[]
    for row in candidates:
        captions,error=_captions(row["video_id"],list(languages))
        record={**row,"captions_available":captions is not None,
                "caption_error":error,"captions":captions,
                "review_state":"PENDING_HUMAN_REVIEW",
                "use_policy":"research reference only; no voice cloning, training ingestion or code execution without rights review"}
        results.append(record)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    payload={"schema":"astra-youtube-research/v1","engine":root.name.lower(),
             "query":query,"created_at":datetime.now(timezone.utc).isoformat(),
             "videos_found":len(results),"videos_with_captions":sum(bool(x["captions_available"]) for x in results),
             "results":results,"errors":errors[:30],
             "limitations":["No video/audio files are downloaded.",
               "Only publicly available captions are attempted.",
               "Caption absence is not a failure of the engine; many videos have no captions.",
               "YouTube discovery/transcript availability can change and may be rate limited.",
               "All content remains untrusted evidence pending review."]}
    out=research_dir/f"youtube-{stamp}.json"
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    handoff=inbox_dir/f"youtube-{stamp}.json"
    handoff.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    payload["research_file"]=str(out); payload["handoff_file"]=str(handoff)
    session.close()
    return payload
