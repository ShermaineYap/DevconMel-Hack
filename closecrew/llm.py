"""Optional language model for plain-English narration.

Money decisions are deterministic and audited. The model is only used for
wording, and the Explainer rejects its text if it mentions any amount that
the Auditor did not produce. Works with no key at all (template fallback).

Env vars (pick one):
  ANTHROPIC_API_KEY  [+ CLOSECREW_MODEL, default claude-sonnet-5-5]
  OPENAI_API_KEY     [+ OPENAI_BASE_URL for any OpenAI-compatible host, CLOSECREW_MODEL]
"""

from __future__ import annotations

import os

import httpx


def available() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return ""


def complete(system: str, prompt: str, max_tokens: int = 400) -> str:
    provider = available()
    if not provider:
        return ""
    try:
        if provider == "anthropic":
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=30, headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                "content-type": "application/json"}, json={
                "model": os.environ.get("CLOSECREW_MODEL", "claude-sonnet-5-5"), "max_tokens": max_tokens,
                "system": system, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json().get("content", []))
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        r = httpx.post(f"{base}/chat/completions", timeout=30,
                       headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                       json={"model": os.environ.get("CLOSECREW_MODEL", "gpt-4.1-mini"), "max_tokens": max_tokens,
                             "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:  # narration is optional; never break the close over it
        return ""
