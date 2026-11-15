"""Confirm that every summarised paragraph is still published by its source.

The corpus stores summaries written by the OrbitVitals team, not source text. For each
entry it records the SHA-256 digest of the summarised paragraph (whitespace collapsed).
This script downloads each source document, computes the digest of every paragraph-like
block, and reports whether the recorded digest is among them. Document text is held in
memory only; nothing from a source is written to disk or printed.

A source is a NASA web page (fetched at its URL) or an open-access article (fetched as
full-text XML from the Europe PMC REST service named in `verification_url`; the entry's
`url` is the DOI link shown to readers).

Usage, from `ai_agent/` (network access required, about 25 requests):

    python -m scripts.verify_sources

Exits with status 1 when a summary digest is wrong or a source paragraph is no longer
found. When that happens, re-read the source and update the summary by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

CORPUS_PATH = (
    Path(__file__).resolve().parents[1]
    / "orbit_agent"
    / "evidence"
    / "corpus"
    / "evidence_summaries.json"
)

_TEXT_BLOCKS = {"p", "li", "td", "blockquote"}
_IGNORED = {"script", "style", "noscript", "svg", "nav", "footer", "form"}
_USER_AGENT = "Mozilla/5.0 (compatible; evidence-source-check)"
# Downloads of large pages occasionally time out; each source is tried this many times.
_ATTEMPTS = 3


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
    document = ""
    for attempt in range(_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310 - allow-listed
                if urlparse(response.geturl()).hostname not in allowed_hosts:
                    raise ValueError(f"Redirected outside the allow-list: {response.geturl()}")
                document = response.read().decode("utf-8", errors="replace")
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == _ATTEMPTS - 1:
                raise ConnectionError(f"Cannot download {url}: {error}") from error
    extractor = _BlockExtractor()
    extractor.feed(document)
    return {sha256_text(block) for block in extractor.blocks}


def check(corpus_path: Path = CORPUS_PATH) -> int:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    documents: dict[str, set[str] | None] = {}
    failures = 0
    for entry in corpus["passages"]:
        url = entry.get("verification_url") or entry["url"]
        if url not in documents:
            try:
                documents[url] = page_block_digests(url, corpus["allowed_hosts"])
            except ConnectionError as error:
                print(f"WARN {error}")
                documents[url] = None
        digests = documents[url]
        summary_ok = sha256_text(entry["text"]) == entry["sha256"]
        found = digests is not None and entry["source_paragraph_sha256"] in digests
        if not (summary_ok and found):
            failures += 1
        state = (
            "source not reachable"
            if digests is None
            else "found"
            if found
            else "not found in the source"
        )
        print(
            f"{'ok  ' if summary_ok and found else 'FAIL'} {entry['evidence_id']} "
            f"summary-digest={'ok' if summary_ok else 'mismatch'} source-paragraph={state}"
        )
    total = len(corpus["passages"])
    print(f"{total - failures}/{total} entries verified against {len(documents)} sources")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    return check()


if __name__ == "__main__":
    sys.exit(main())
