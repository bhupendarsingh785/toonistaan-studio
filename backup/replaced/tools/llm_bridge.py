#!/usr/bin/env python3
"""ASTRA LLM Bridge v2 — backward-compatible, resilient OpenAI-compatible gateway.

Existing public functions remain: status(), ready_providers(), chat(), remember().
No SDK dependency; HTTP uses Python's standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"

PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {"base": "https://api.openai.com/v1", "env": "OPENAI_API_KEY", "model": "gpt-4o-mini"},
    "groq": {"base": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY", "model": "openai/gpt-oss-120b"},
    "openrouter": {"base": "https://openrouter.ai/api/v1", "env": "OPENROUTER_API_KEY", "model": "openai/gpt-4o-mini"},
    "together": {"base": "https://api.together.xyz/v1", "env": "TOGETHER_API_KEY", "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    "ollama": {"base": "http://127.0.0.1:11434/v1", "env": None, "model": "llama3.1"},
    "custom": {"base": "", "env": "LLM_API_KEY", "model": ""},
}
ORDER = ["openai", "groq", "openrouter", "together", "ollama", "custom"]
RETRYABLE_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass
class ProviderState:
    name: str
    ready: bool
    reason: str
    model: str = ""


def _spec(name: str) -> dict[str, Any] | None:
    raw = PROVIDERS.get(name)
    if raw is None:
        return None
    prefix = f"ASTRA_{name.upper()}_"
    base = os.environ.get(prefix + "BASE_URL", raw.get("base", "")).strip().rstrip("/")
    model = os.environ.get(prefix + "MODEL", raw.get("model", "")).strip()
    if name == "custom":
        base = os.environ.get("LLM_BASE_URL", base).strip().rstrip("/")
        model = os.environ.get("LLM_MODEL", model).strip()
    return {"base": base, "env": raw.get("env"), "model": model}


def _key(env: str | None) -> str | None:
    value = os.environ.get(env, "").strip() if env else ""
    return value or None


def _valid_base(base: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(base)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def _request(method: str, url: str, payload: dict | None = None,
             key: str | None = None, timeout: float = 30.0) -> dict:
    if timeout <= 0:
        raise ValueError("timeout positive hona chahiye")
    headers = {"Accept": "application/json", "User-Agent": "ASTRA-llm-bridge/2"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                raise RuntimeError("provider ne JSON object nahi diya")
            return parsed
    except urllib.error.HTTPError as exc:
        # Never print response body: it can contain private request details.
        retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
        suffix = f"; retry-after={retry_after}" if retry_after.isdigit() else ""
        raise RuntimeError(f"HTTP {exc.code}{suffix}") from None
    except urllib.error.URLError as exc:
        reason = exc.reason
        raise RuntimeError(f"network error: {type(reason).__name__}") from None
    except TimeoutError:
        raise RuntimeError("request timed out") from None
    except json.JSONDecodeError:
        raise RuntimeError("provider ka response valid JSON nahi tha") from None


def _probe(base: str, key: str | None = None, timeout: float = 3.0) -> tuple[bool, str]:
    if not _valid_base(base):
        return False, "invalid/missing HTTP(S) base URL"
    try:
        _request("GET", base + "/models", key=key, timeout=timeout)
        return True, "models endpoint reachable"
    except Exception as exc:
        return False, str(exc)[:120]


def status(probe: bool = True, timeout: float = 3.0) -> list[ProviderState]:
    """Live reachability by default; probe=False checks configuration only."""
    states: list[ProviderState] = []
    for name in ORDER:
        spec = _spec(name)
        if spec is None:
            continue
        base, env, model = spec["base"], spec["env"], spec["model"]
        key = _key(env)
        if not _valid_base(base):
            states.append(ProviderState(name, False, "valid HTTP(S) base URL nahi", model))
        elif env and not key:
            states.append(ProviderState(name, False, f"{env} nahi mila", model))
        elif not model:
            states.append(ProviderState(name, False, "model set nahi", model))
        elif not probe:
            states.append(ProviderState(name, True, "configuration present; live check skipped", model))
        else:
            ok, reason = _probe(base, key, timeout)
            states.append(ProviderState(name, ok, reason, model))
    return states


def ready_providers() -> list[str]:
    return [state.name for state in status() if state.ready]


def _post(url: str, payload: dict, key: str | None, timeout: int = 90) -> dict:
    return _request("POST", url, payload=payload, key=key, timeout=timeout)


def _content(data: dict) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("provider response mein choices nahi hain")
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}:
                value = part.get("text", "")
                if isinstance(value, str):
                    chunks.append(value)
        return "".join(chunks).strip()
    return ""


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in RETRYABLE_HTTP
    message = str(exc).lower()
    return any(word in message for word in ("network error", "timed out", "temporarily unavailable"))


def _attempt_chat(base: str, key: str | None, payload: dict, timeout: int,
                  retries: int) -> dict:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return _post(base + "/chat/completions", payload, key, timeout)
        except Exception as exc:
            last = exc
            if attempt >= retries or not _retryable(exc):
                raise
            # Short bounded backoff; never sleeps for a provider-supplied long delay.
            time.sleep(min(0.5 * (2 ** attempt), 2.0))
    assert last is not None
    raise last


def chat(messages: list[dict], provider: str | None = None, model: str | None = None,
         temperature: float = 0.6, timeout: int = 90,
         max_tokens: int | None = None, retries: int = 1) -> tuple[str, dict]:
    """Send chat request; explicit provider first, then configured fallbacks.

    An explicitly supplied model applies only to the explicitly selected provider.
    Fallback providers use their own configured model to avoid cross-provider model IDs.
    """
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages non-empty list honi chahiye")
    for index, item in enumerate(messages):
        if not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"messages[{index}] ka role invalid hai")
        if not isinstance(item.get("content"), (str, list)):
            raise ValueError(f"messages[{index}].content invalid hai")
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        raise ValueError("temperature numeric honi chahiye") from None
    if not 0 <= temperature <= 2:
        raise ValueError("temperature 0 se 2 ke beech honi chahiye")
    if timeout <= 0 or retries < 0 or retries > 3:
        raise ValueError("timeout positive aur retries 0 se 3 ke beech hone chahiye")
    if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens < 1):
        raise ValueError("max_tokens positive integer hona chahiye")
    if provider and provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; options: {', '.join(ORDER)}")

    chain = ([provider] if provider else []) + [name for name in ORDER if name != provider]
    attempts: list[dict] = []
    for name in chain:
        spec = _spec(name)
        if spec is None:
            continue
        base, env = spec["base"], spec["env"]
        key = _key(env)
        # Only explicit target gets caller's model override.
        use_model = (model if provider == name and model else spec["model"])
        if not _valid_base(base) or (env and not key) or not use_model:
            attempts.append({"provider": name, "ok": False, "note": "configuration incomplete"})
            continue
        payload: dict[str, Any] = {
            "model": use_model, "messages": messages, "temperature": temperature
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            data = _attempt_chat(base, key, payload, timeout, retries)
            answer = _content(data)
            if not answer:
                attempts.append({"provider": name, "ok": False, "note": "empty response"})
                continue
            attempts.append({"provider": name, "ok": True, "note": use_model})
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            return answer, {
                "provider": name, "model": use_model, "tries": attempts,
                "usage": usage, "request_id": data.get("id"),
                "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason")
            }
        except Exception as exc:
            attempts.append({"provider": name, "ok": False,
                             "note": f"{type(exc).__name__}: {str(exc)[:100]}"})
    raise RuntimeError("all configured providers failed: " + json.dumps(attempts, ensure_ascii=False))


def remember(question: str, answer: str, provider: str = "") -> Path:
    """Append a retrieval note; this does not train or update model weights."""
    if not isinstance(question, str) or not isinstance(answer, str) or not question.strip() or not answer.strip():
        raise ValueError("question aur answer non-empty text hone chahiye")
    KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    path = KNOWLEDGE / "seekha-hua.md"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {stamp} · {provider or 'llm'}\n"
                 f"**Sawaal:** {question.strip()[:400]}\n\n"
                 f"**Jawab:** {answer.strip()[:1500]}\n")
    return path


def cmd_status() -> int:
    states = status()
    for state in states:
        mark = "[READY]" if state.ready else "[ --  ]"
        print(f"{mark} {state.name:11s} {state.reason:34s} {state.model}")
    ready = [state.name for state in states if state.ready]
    print(f"\nChain: {' -> '.join(ORDER)}")
    print(f"Abhi reachable: {', '.join(ready) if ready else 'koi nahi (key/server check karo)'}")
    return 0 if ready else 1


def cmd_chat(text: str, provider: str | None, remember_it: bool) -> int:
    messages = [
        {"role": "system", "content": "Tum ASTRA ke sahayak ho. Hindi/Hinglish me seedha, saaf jawab do."},
        {"role": "user", "content": text},
    ]
    try:
        answer, meta = chat(messages, provider=provider)
    except Exception as exc:
        print(f"[x] {exc}")
        return 1
    print(answer)
    print(f"\n— {meta['provider']} / {meta['model']}")
    if remember_it:
        print(f"[memory] {remember(text, answer, meta['provider']).relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ASTRA LLM bridge (multi-provider)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("models")
    chat_parser = sub.add_parser("chat")
    chat_parser.add_argument("text")
    chat_parser.add_argument("--provider")
    chat_parser.add_argument("--remember", action="store_true")
    file_parser = sub.add_parser("ask-file")
    file_parser.add_argument("path")
    file_parser.add_argument("--provider")
    file_parser.add_argument("--out")
    args = parser.parse_args()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "models":
        print(json.dumps({name: _spec(name)["model"] for name in ORDER}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "chat":
        return cmd_chat(args.text, args.provider, args.remember)
    try:
        question = Path(args.path).read_text(encoding="utf-8")
        answer, _meta = chat([{"role": "user", "content": question}], provider=args.provider)
        if args.out:
            Path(args.out).write_text(answer, encoding="utf-8")
            print(f"likh diya: {args.out}")
        else:
            print(answer)
        return 0
    except Exception as exc:
        print(f"[x] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
