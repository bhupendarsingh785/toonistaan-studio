
"""Engine-owned browser/research collector with conservative safety controls."""
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from pathlib import Path
import requests, hashlib, time, re, json

UA = "IndependentHindiVoiceResearch/0.3"
MAX_BYTES = 2_000_000
def _robots_allowed(url):
    u = urlparse(url); robots = f"{u.scheme}://{u.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots); rp.read()
        return rp.can_fetch(UA, url), robots
    except Exception:
        return False, robots

def clean_html_text(txt):
    txt=re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>"," ",txt)
    txt=re.sub(r"(?s)<[^>]+>"," ",txt)
    txt=re.sub(r"\s+"," ",txt)
    return txt.strip()

def collect(url, allowed_domains=None):
    u = urlparse(url)
    if u.scheme not in ("http","https") or not u.hostname:
        raise ValueError("Only absolute http/https URLs are accepted.")
    if allowed_domains and u.hostname not in allowed_domains:
        raise PermissionError("This domain is not in the engine's allowlist.")
    allowed, robots_url = _robots_allowed(url)
    if not allowed:
        raise PermissionError(f"robots.txt disallows or could not be verified: {robots_url}")
    r = requests.get(url, headers={"User-Agent":UA}, timeout=(8,20), stream=True)
    r.raise_for_status()
    content=[]; total=0
    for chunk in r.iter_content(65536):
        total += len(chunk)
        if total > MAX_BYTES: raise ValueError("Response exceeded 2 MB safety limit.")
        content.append(chunk)
    raw=b"".join(content)
    ctype=r.headers.get("content-type","")
    if not any(x in ctype for x in ("text/","html","json","xml")):
        raise ValueError("Non-text response rejected.")
    txt=raw.decode(r.encoding or "utf-8",errors="replace")
    if "html" in ctype:
        txt=clean_html_text(txt)
    return {"url":url,"domain":u.hostname,"collected_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
            "content_type":ctype,"sha256":hashlib.sha256(raw).hexdigest(),"text":txt[:150000],
            "verification":"URL and robots policy checked; factual truth still requires independent corroboration."}

def browser_collect(url, allowed_domains=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return collect(url, allowed_domains)
    u=urlparse(url)
    if allowed_domains and u.hostname not in allowed_domains:
        raise PermissionError("Domain not allowlisted.")
    allowed, robots_url = _robots_allowed(url)
    if not allowed: raise PermissionError(f"robots.txt disallows or could not be verified: {robots_url}")
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(user_agent=UA)
        page.goto(url,wait_until="domcontentloaded",timeout=25000)
        title=page.title(); body=page.locator("body").inner_text(timeout=7000)
        browser.close()
    return {"url":url,"domain":u.hostname,"title":title,"text":body[:150000],
            "collected_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
            "sha256":hashlib.sha256(body.encode()).hexdigest(),
            "verification":"Browser-rendered text; facts require independent corroboration."}
