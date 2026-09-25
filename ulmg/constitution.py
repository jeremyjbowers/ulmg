# ABOUTME: Fetch, parse, and search the ULMG constitution from Google Docs pub HTML.
# ABOUTME: Live network fetch is only for the refresh command; reads use the DB cache.
from __future__ import annotations

import hashlib
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

CONSTITUTION_PUB_URL = (
    "https://docs.google.com/document/d/e/"
    "2PACX-1vQmtw4gpA19fxNIFbSQZrF22z92eYbbhWPd_11PmH9fr2_vCUjTrMqZh_J2ySre0qrxKv_qtK-E9BTh"
    "/pub"
)

DEFAULT_CONTEXT_CHARS = 180
MAX_SEARCH_MATCHES = 40


def extract_constitution_text(html: str) -> str:
    """Pull plain text from the Google Docs pub `#contents` container."""
    soup = BeautifulSoup(html, "html.parser")
    contents = soup.select_one("#contents")
    if contents is None:
        raise ValueError("Could not find #contents in constitution HTML")
    text = contents.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise ValueError("Constitution #contents was empty")
    return text


def fetch_constitution_html(url: str = CONSTITUTION_PUB_URL, timeout: int = 60) -> str:
    """Download the public Google Docs HTML (used only by refresh)."""
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "ulmg-constitution-refresh/1.0"},
    )
    resp.raise_for_status()
    return resp.content.decode("utf-8", errors="replace")


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def search_constitution_text(
    text: str,
    query: str,
    *,
    context_chars: int = DEFAULT_CONTEXT_CHARS,
    limit: int = MAX_SEARCH_MATCHES,
) -> list[dict]:
    """
    Case-insensitive substring search returning excerpts with surrounding context.
    """
    q = (query or "").strip()
    if not q or not text:
        return []

    haystack = text.lower()
    needle = q.lower()
    matches: list[dict] = []
    start = 0
    while len(matches) < limit:
        idx = haystack.find(needle, start)
        if idx < 0:
            break
        left = max(0, idx - context_chars)
        right = min(len(text), idx + len(q) + context_chars)
        excerpt = text[left:right]
        if left > 0:
            excerpt = "…" + excerpt
        if right < len(text):
            excerpt = excerpt + "…"
        matches.append(
            {
                "query": q,
                "offset": idx,
                "excerpt": excerpt,
            }
        )
        start = idx + max(len(needle), 1)
    return matches


def load_text_from_path(path: str) -> str:
    """
    Load constitution text from a local file.
    HTML files are parsed via #contents; .txt files are used as-is.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    lower = path.lower()
    if lower.endswith((".html", ".htm")) or "<html" in raw[:500].lower():
        return extract_constitution_text(raw)
    return raw.strip()
