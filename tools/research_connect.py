#!/usr/bin/env python3
"""Research Connect — agents ke liye asli internet (bina key, bina paid API).

Kaam:
  1) search()  — DuckDuckGo (html) se links; fail ho to Wikipedia API
  2) fetch()   — page ka saaf text (tags hatakar), 20k char tak
  3) research()— poora kaam: query -> sources[] (url, domain, title, text, sha256, status)
  4) retry + fallback: ek jagah fail ho to doosri (agent khali haath wapas nahi jata)

CLI:
  python tools/research_connect.py "piper tts hindi voice" --max 5
"""
from __future__ import annotations
import argparse, hashlib, html, json, re, sys, time
import urllib.parse, urllib.request
from pathlib import Path

UA = "astra-research/1.0 (+https://github.com/bhupendarsingh/who)"
TIMEOUT = 25


def _get(url: str, tries: int = 2) -> str | None:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(600000)
            try:
                return raw.decode("utf-8", "ignore")
            except Exception:
                return raw.decode("latin-1", "ignore")
        except Exception:
            if i + 1 < tries:
                time.sleep(1.2 * (i + 1))
    return None


def _clean(text: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def search_ddg(query: str, limit: int = 6) -> list[dict]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    body = _get(url)
    if not body:
        return []
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S):
        href, title = m.group(1), _clean(m.group(2))
        if "uddg=" in href:
            href = urllib.parse.unquote(re.search(r"uddg=([^&]+)", href).group(1))
        if not href.startswith("http") or href in seen:
            continue
        seen.add(href)
        out.append({"url": href, "title": title or href})
        if len(out) >= limit:
            break
    return out


def search_wiki(query: str, limit: int = 5) -> list[dict]:
    api = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
           f"&srsearch={urllib.parse.quote_plus(query)}&srlimit={limit}")
    body = _get(api)
    if not body:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    out = []
    for row in data.get("query", {}).get("search", [])[:limit]:
        title = row.get("title", "")
        out.append({"url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                    "title": title})
    return out


def search_github(query: str, limit: int = 5) -> list[dict]:
    """GitHub search — tech/engine ke liye sabse kaam ka (bina key, 10 req/min)."""
    url = ("https://api.github.com/search/repositories?per_page="
           f"{limit}&q={urllib.parse.quote_plus(query)}")
    body = _get(url)
    if not body:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    return [{"url": it.get("html_url", ""), "title": it.get("full_name", ""),
             "note": (it.get("description") or "")[:160]}
            for it in data.get("items", [])[:limit] if it.get("html_url")]


def search_arxiv(query: str, limit: int = 4) -> list[dict]:
    """arXiv — research papers (TTS/voice ke liye)."""
    phrase = urllib.parse.quote_plus('"' + " ".join(query.split()[:4]) + '"')
    url = ("http://export.arxiv.org/api/query?max_results="
           f"{limit * 3}&search_query=all:{phrase}")
    body = _get(url)
    if not body or "<entry>" not in body:
        url = ("http://export.arxiv.org/api/query?max_results="
               f"{limit * 3}&search_query=all:{urllib.parse.quote_plus(query)}")
        body = _get(url)
    if not body:
        return []
    out = []
    for m in re.finditer(r"<entry>.*?<id>(.*?)</id>.*?<title>(.*?)</title>.*?<summary>(.*?)</summary>",
                         body, re.S):
        out.append({"url": m.group(1).strip(), "title": _clean(m.group(2))[:140],
                    "text": _clean(m.group(3))[:4000]})
    return out[:limit]


def wiki_extract(title: str, lang: str = "en") -> str:
    api = (f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1"
           f"&format=json&titles={urllib.parse.quote(title)}")
    body = _get(api)
    if not body:
        return ""
    try:
        pages = json.loads(body).get("query", {}).get("pages", {})
        for _, pg in pages.items():
            return (pg.get("extract") or "")[:8000]
    except Exception:
        return ""
    return ""


def search_news(query: str, limit: int = 6) -> list[dict]:
    """Google News RSS + The Hindu RSS — asli khabar (bina key). India ke liye."""
    out, seen = [], set()
    feeds = [
        "https://news.google.com/rss/search?hl=en-IN&gl=IN&ceid=IN:en&q=" + urllib.parse.quote_plus(query),
        "https://www.thehindu.com/news/national/feeder/default.rss",
    ]
    for url in feeds:
        body = _get(url)
        if not body:
            continue
        for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
            block = m.group(1)
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
            l = re.search(r"<link>(.*?)</link>", block, re.S)
            d = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", block, re.S)
            src = re.search(r'<source url="(https?://[^"]+)"', block)
            if not l:
                continue
            link = _clean(l.group(1))
            if not link.startswith("http") or link in seen:
                continue
            seen.add(link)
            pub = urllib.parse.urlparse(src.group(1)).hostname if src else ""
            out.append({"url": link, "title": _clean(t.group(1)) if t else link,
                        "text": _clean(d.group(1))[:3000] if d else "",
                        "domain": pub})
            if len(out) >= limit:
                return out
    return out


def search_wiki_hi(query: str, limit: int = 4) -> list[dict]:
    api = ("https://hi.wikipedia.org/w/api.php?action=query&list=search&format=json"
           f"&srsearch={urllib.parse.quote_plus(query)}&srlimit={limit}")
    body = _get(api)
    if not body:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    return [{"url": "https://hi.wikipedia.org/wiki/" + urllib.parse.quote(r.get("title", "").replace(" ", "_")),
             "title": r.get("title", "")} for r in data.get("query", {}).get("search", [])[:limit]]


SEARCH_ORDER = (("news", search_news), ("github", search_github), ("wikipedia", search_wiki),
                ("arxiv", search_arxiv), ("wikipedia_hi", search_wiki_hi),
                ("duckduckgo", search_ddg))


def search_all(query: str, limit: int = 6) -> list[dict]:
    """Har source try karo (jab tak limit na bhare) — ek fail ho to doosra."""
    out, seen, used = [], set(), []
    for name, fn in SEARCH_ORDER:
        if len(out) >= limit:
            break
        try:
            hits = fn(query, limit)
        except Exception:
            continue
        if hits:
            used.append(name)
        for h in hits:
            if h["url"] in seen:
                continue
            seen.add(h["url"])
            out.append(h)
    return [{"engine": "+".join(used) or "none", "results": out[:limit]}]


def search(query: str, limit: int = 6) -> dict:
    res = search_all(query, limit)
    return res[0] if res else {"engine": "none", "results": []}


def fetch(url: str, max_chars: int = 20000) -> dict:
    body = _get(url)
    if not body:
        return {"url": url, "status": "failed", "reason": "fetch fail", "text": ""}
    text = _clean(body)[:max_chars]
    if len(text) < 120:
        return {"url": url, "status": "failed", "reason": "text bahut kam", "text": text}
    return {"url": url, "status": "collected", "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest()}


STOP = {"the", "and", "for", "with", "quality", "using", "from", "that", "this",
        "control", "natural", "better", "best"}
# project ke asli shabd — title me inme se koi na ho to result bekaar hai
CORE_WORDS = {"tts", "speech", "voice", "voices", "prosody", "audio", "hindi", "piper",
              "espeak", "edge", "synthesis", "synthesizer", "clone", "cloning", "emotion",
              "emotional", "pitch", "mel", "vocoder", "speaker", "phoneme", "prosodic"}


def _relevant(hit: dict, query: str) -> bool:
    """Sirf kaam ka result — query ke shabd title/text me hone chahiye (2+)."""
    words = {w for w in re.split(r"[^a-z0-9]+", query.lower()) if len(w) > 3 and w not in STOP}
    if not words:
        return True
    blob = (str(hit.get("title", "")) + " " + str(hit.get("text", ""))).lower()
    in_title = sum(1 for w in words if w in str(hit.get("title", "")).lower())
    total = sum(1 for w in words if w in blob)
    title_l = str(hit.get("title", "")).lower()
    has_core = any(w in title_l for w in CORE_WORDS)
    if not has_core and total < 3:
        return False
    return total >= 2 or in_title >= 1 or (total >= 1 and len(words) <= 3)


def research(query: str, max_sources: int = 5, max_chars: int = 20000) -> dict:
    """Ek query par asli sources — schema wahi jo engine agents use karte hain."""
    found = search(query, limit=max_sources * 2)
    sources, used = [], 0
    for hit in found["results"]:
        if used >= max_sources:
            break
        if not _relevant(hit, query):
            continue
        if hit.get("text"):
            got = {"status": "collected", "text": hit["text"][:max_chars],
                   "sha256": hashlib.sha256(hit["text"][:max_chars].encode()).hexdigest()}
        elif "wikipedia.org/wiki/" in hit["url"]:
            lang = "hi" if "hi.wikipedia" in hit["url"] else "en"
            title = urllib.parse.unquote(hit["url"].split("/wiki/")[-1]).replace("_", " ")
            ex = wiki_extract(title, lang)
            got = ({"status": "collected", "text": ex[:max_chars],
                    "sha256": hashlib.sha256(ex[:max_chars].encode()).hexdigest()}
                   if len(ex) > 200 else fetch(hit["url"], max_chars))
        else:
            got = fetch(hit["url"], max_chars)
        domain = hit.get("domain") or urllib.parse.urlparse(hit["url"]).hostname or ""
        row = {"url": hit["url"], "domain": domain, "title": hit["title"],
               "text": got.get("text", ""), "sha256": got.get("sha256", ""),
               "relevance": "search_match", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "status": got["status"], "reason": got.get("reason", "")}
        sources.append(row)
        if got["status"] == "collected":
            used += 1
    return {"query": query, "search_engine": found["engine"],
            "candidate_count": len(found["results"]),
            "collected_count": used, "sources": sources}


def main() -> int:
    ap = argparse.ArgumentParser(description="agents ke liye internet (bina key)")
    ap.add_argument("query")
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rep = research(a.query, a.max)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("query", "search_engine", "candidate_count", "collected_count")},
                     ensure_ascii=False))
    for s in rep["sources"][:5]:
        print(f"  {s['status']:9s} {s['domain'][:28]:30s} {s['title'][:40]}")
    return 0 if rep["collected_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
