"""Search module for the search engine tool.

Implements the read-side operations on a built :class:`Index`:

  * :func:`print_term` - the ``print`` CLI command. Pretty-prints the
    inverted-index entry for a single word.

  * :func:`find` - the ``find`` CLI command. Returns the URLs of pages that
    contain every word in the query (conjunctive / AND semantics).

The AND default mirrors Google's behaviour and the natural reading of
``find good friends`` ("pages mentioning *both* good and friends"). An OR
or ranked variant could be added later without changing the index format;
we discuss this trade-off in the demo.
"""
from __future__ import annotations

from .indexer import Index
from .tokeniser import tokenise


_POSITIONS_PREVIEW = 10  # cap on positions shown by print_term per posting


def print_term(index: Index, word: str) -> None:
    """Pretty-print the inverted-index entry for a single word.

    The query is normalised through the same lowercase rule used at index
    build time, so ``Print Good`` works the same as ``print good``.
    """
    term = word.lower()
    entry = index.get(term)
    if entry is None:
        print(f"'{term}' is not in the index.")
        return

    print(f"Term: {term}")
    print(f"  Document frequency: {entry['doc_freq']}")
    print("  Postings:")
    for doc_id in sorted(entry["postings"]):
        posting = entry["postings"][doc_id]
        url = index.documents.get(doc_id, "<unknown>")
        positions = posting["positions"]
        if len(positions) > _POSITIONS_PREVIEW:
            shown = ", ".join(str(p) for p in positions[:_POSITIONS_PREVIEW])
            preview = f"[{shown}, ... ({len(positions)} total)]"
        else:
            preview = "[" + ", ".join(str(p) for p in positions) + "]"
        print(f"    doc {doc_id} ({url}): tf={posting['tf']}, positions={preview}")


def find(index: Index, words: list[str]) -> list[str]:
    """Return URLs of pages containing **all** of the given words.

    Each input word is run through the same tokeniser used at build time,
    so quirky punctuation or casing in the query is handled consistently
    (e.g. ``find Good!`` matches the indexed term ``good``). If the query
    is empty after tokenisation, or any term is missing from the index,
    the result is an empty list.
    """
    terms: list[str] = []
    for w in words:
        terms.extend(tokenise(w))
    if not terms:
        return []

    posting_sets: list[set[int]] = []
    for term in terms:
        entry = index.get(term)
        if entry is None:
            return []  # AND semantics: any missing term -> no results
        posting_sets.append(set(entry["postings"].keys()))

    matched = set.intersection(*posting_sets)
    return [index.documents[doc_id] for doc_id in sorted(matched)]
