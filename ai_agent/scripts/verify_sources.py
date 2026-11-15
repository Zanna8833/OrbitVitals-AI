"""Confirm that every summarised NASA paragraph is still published at its source URL.

The corpus stores summaries written by the OrbitVitals team, not NASA text. For each
entry it records the SHA-256 digest of the summarised paragraph (whitespace collapsed).
This script downloads each source page, computes the digest of every paragraph-like
block, and reports whether the recorded digest is among them. Page text is held in
memory only; nothing from the page is written to disk or printed.

Usage, from `ai_agent/` (network access required):

    python -m scripts.verify_sources

Exits with status 1 when a summary digest is wrong or a source paragraph is no longer
found on its page. When that happens, re-read the page and update the summary by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

CORPUS_PATH = (
    Path(__file__).resolve().parents[1]
    / "orbit_agent"
    / "evidence"
    / "corpus"
    / "nasa_summaries.json"
)

_TEXT_BLOCKS = {"p", "li", "td", "blockquote"}
_IGNORED = {"script", "style", "noscript", "svg", "nav", "footer", "form"}
_USER_AGENT = "Mozilla/5.0 (compatible; evidence-source-check)"


class _BlockExtractor(html.parser.HTMLParser):
    """Collect the text of paragraph-like elements, with whitespace collapsed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._ignored_depth = 0
        self._open_tag: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORED:
            self._ignored_depth += 1
        elif tag in _TEXT_BLOCKS and self._ignored_depth == 0 and self._open_tag is None:
            self._open_tag = tag
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORED and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == self._open_tag:
            text = " ".join("".join(self._parts).split())
            if text:
                self.blocks.append(text)
            self._open_tag = None

    def handle_data(self, data: str) -> None:
        if self._open_tag is not None and self._ignored_depth == 0:
            self._parts.append(data)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_block_digests(url: str, allowed_hosts: list[str]) -> set[str]:
    """Download `url` and return the digests of its paragraph-like blocks."""
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in allowed_hosts:
        raise ValueError(f"URL is not on the allow-list: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - allow-listed
        if urlparse(response.geturl()).hostname not in allowed_hosts:
            raise ValueError(f"Redirected outside the allow-list: {response.geturl()}")
        document = response.read().decode("utf-8", errors="replace")
    extractor = _BlockExtractor()
    extractor.feed(document)
    return {sha256_text(block) for block in extractor.blocks}


def check(corpus_path: Path = CORPUS_PATH) -> int:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    pages: dict[str, set[str]] = {}
    failures = 0
    for entry in corpus["passages"]:
        url = entry["url"]
        if url not in pages:
            pages[url] = page_block_digests(url, corpus["allowed_hosts"])
        summary_ok = sha256_text(entry["text"]) == entry["sha256"]
        found = entry["source_paragraph_sha256"] in pages[url]
        if not (summary_ok and found):
            failures += 1
        print(
            f"{'ok  ' if summary_ok and found else 'FAIL'} {entry['evidence_id']} "
            f"summary-digest={'ok' if summary_ok else 'mismatch'} "
            f"source-paragraph={'found' if found else 'not found on page'}"
        )
    total = len(corpus["passages"])
    print(f"{total - failures}/{total} entries verified against {len(pages)} source pages")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    return check()


if __name__ == "__main__":
    sys.exit(main())
