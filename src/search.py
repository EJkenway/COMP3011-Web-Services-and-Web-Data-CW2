"""Search module for the search engine tool.

Implements the read-side operations on a built :class:`Index`:

  * :func:`print_term` - the ``print`` CLI command. Pretty-prints the
    inverted-index entry for a single word.

  * :func:`find` - the ``find`` CLI command. Returns the URLs of pages
    containing every query word (AND semantics), ranked by TF-IDF
    relevance score.

The TF-IDF score for a document ``d`` against query ``Q`` is::

    score(d) = sum_{t in Q} tf(t, d) * log(N / df(t))

where ``N`` is the number of documents and ``df(t)`` is the document
frequency of term ``t``. Documents are ranked highest-first; ties are
broken deterministically by ascending ``doc_id``.

The AND filter runs *before* scoring so the result set never shrinks
beyond what conjunctive processing already promises - rare-term queries
remain fast and TF-IDF is computed only over the small candidate set.
"""
from __future__ import annotations

import math

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
    """Return URLs of pages containing **all** query words, ranked by TF-IDF.

    Each input word is run through the same tokeniser used at build time,
    so capitalisation or punctuation in the query is handled consistently
    (e.g. ``find Good!`` matches the indexed term ``good``). If the query
    is empty after tokenisation, or any term is missing from the index,
    the result is an empty list.

    Ranking: ``score(d) = sum_t tf(t, d) * log(N / df(t))``. Documents
    with equal scores are ordered by ascending ``doc_id`` so the output
    is deterministic across runs.
    """
    terms: list[str] = []
    for w in words:
        terms.extend(tokenise(w))
    if not terms:
        return []

    # Look up each term once; short-circuit AND on any missing term.
    entries = []
    for term in terms:
        entry = index.get(term)
        if entry is None:
            return []
        entries.append(entry)

    # AND filter: candidate doc_ids = intersection of every term's postings.
    candidates = set.intersection(
        *(set(entry["postings"].keys()) for entry in entries)
    )
    if not candidates:
        return []

    # TF-IDF scoring across the candidate set only.
    n_docs = index.num_documents
    scores: dict[int, float] = {}
    for entry in entries:
        df = entry["doc_freq"]
        idf = math.log(n_docs / df) if df else 0.0
        for doc_id in candidates:
            tf = entry["postings"][doc_id]["tf"]
            scores[doc_id] = scores.get(doc_id, 0.0) + tf * idf

    # Sort by score descending; tie-break by ascending doc_id.
    ranked = sorted(scores, key=lambda d: (-scores[d], d))
    return [index.documents[d] for d in ranked]
