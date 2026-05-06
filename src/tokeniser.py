"""Text-extraction and tokenisation helpers for the indexer.

Two responsibilities, one per public function:
  * ``extract_text``  - strip HTML markup, return the visible text of a page.
  * ``tokenise``      - split text into lowercase alphanumeric tokens.

Keeping these separate from the indexer lets us reuse them in tests with
synthetic HTML, and lets us swap the tokenisation strategy (e.g. add stemming)
without touching the indexer.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup


# A token is one or more alphanumeric characters. Punctuation, whitespace, and
# any other character act as token boundaries. Apostrophes split contractions
# (don't -> don, t) which is acceptable for this coursework; the trade-off is
# discussed in the README and the demo video.
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def extract_text(html: str) -> str:
    """Return the human-readable text of an HTML document.

    ``<script>`` and ``<style>`` blocks are removed because they contain code,
    not natural-language content that should appear in the index.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ")


def tokenise(text: str) -> list[str]:
    """Split text into lowercase tokens (runs of letters/digits).

    Lower-casing is required by the coursework brief: the search must treat
    'Good' and 'good' as the same word.
    """
    return _TOKEN_RE.findall(text.lower())


if __name__ == "__main__":
    # Quick smoke test - run with: python -m src.tokeniser
    sample = """
    <html>
      <head>
        <title>Quotes to Scrape</title>
        <style>body { color: red; }</style>
        <script>console.log("ignored");</script>
      </head>
      <body>
        <span class="text">"The world as we have created it is a process of our thinking."</span>
        <small class="author">Albert Einstein</small>
        <a class="tag">change</a>
        <a class="tag">deep-thoughts</a>
      </body>
    </html>
    """
    text = extract_text(sample)
    print("Extracted text:")
    print(repr(text))
    print()
    tokens = tokenise(text)
    print(f"Tokens ({len(tokens)}):")
    print(tokens)
