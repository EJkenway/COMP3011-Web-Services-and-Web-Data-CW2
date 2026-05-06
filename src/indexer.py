"""Inverted-index module for the search engine tool.

The index follows the classical layout described in lecture 12:

    terms = {
        "love": {
            "doc_freq": 8,
            "postings": {
                doc_id: {"tf": 3, "positions": [4, 19, 102]},
                ...
            }
        },
        ...
    }
    documents = {doc_id: url, ...}

Two data-structure decisions worth highlighting in the demo:

  * ``doc_id`` is an integer rather than the raw URL. Inverted lists are
    accessed millions of times during search, so a 4-byte int per posting is
    cheaper than a 50-character URL. URLs live in a single side table.

  * Each posting stores both ``tf`` (term frequency) and the list of
    ``positions``. ``tf`` is enough for simple ranking; ``positions`` opens
    the door to phrase queries and proximity scoring later.

JSON is used for on-disk serialisation. It is human-readable - useful for
markers, for debugging, and for the demo video - at the cost of slightly
larger files than a binary format like pickle. JSON cannot encode integer
keys, so doc_ids are stringified on save and parsed back on load.
"""
from __future__ import annotations

import json
from pathlib import Path

from .tokeniser import extract_text, tokenise


class Index:
    """In-memory inverted index with JSON persistence."""

    def __init__(self) -> None:
        self.terms: dict[str, dict] = {}
        self.documents: dict[int, str] = {}
        self._next_doc_id: int = 1

    @property
    def num_documents(self) -> int:
        return len(self.documents)

    @property
    def vocabulary_size(self) -> int:
        return len(self.terms)

    def __contains__(self, term: str) -> bool:
        return term in self.terms

    def get(self, term: str) -> dict | None:
        """Return ``{doc_freq, postings}`` for ``term``, or None if absent."""
        return self.terms.get(term)

    def add_document(self, url: str, html: str) -> int:
        """Tokenise an HTML page and merge its terms into the index.

        Returns the assigned ``doc_id``. Positions are 0-indexed in the order
        tokens appear in the extracted text.
        """
        doc_id = self._next_doc_id
        self._next_doc_id += 1
        self.documents[doc_id] = url

        tokens = tokenise(extract_text(html))

        # Aggregate this doc's positions per term in one pass before merging
        # back into the global index, to avoid repeated dict lookups.
        local: dict[str, list[int]] = {}
        for position, token in enumerate(tokens):
            local.setdefault(token, []).append(position)

        for term, positions in local.items():
            entry = self.terms.setdefault(term, {"doc_freq": 0, "postings": {}})
            entry["postings"][doc_id] = {"tf": len(positions), "positions": positions}
            entry["doc_freq"] = len(entry["postings"])
        return doc_id

    def save(self, path: str | Path) -> None:
        """Serialise the index to a single JSON file."""
        payload = {
            "documents": {str(k): v for k, v in self.documents.items()},
            "terms": {
                term: {
                    "doc_freq": entry["doc_freq"],
                    "postings": {
                        str(doc_id): posting
                        for doc_id, posting in entry["postings"].items()
                    },
                }
                for term, entry in self.terms.items()
            },
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Index":
        """Reconstruct an index previously written by :meth:`save`."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        index = cls()
        index.documents = {int(k): v for k, v in payload["documents"].items()}
        index.terms = {
            term: {
                "doc_freq": entry["doc_freq"],
                "postings": {
                    int(doc_id): posting
                    for doc_id, posting in entry["postings"].items()
                },
            }
            for term, entry in payload["terms"].items()
        }
        index._next_doc_id = max(index.documents, default=0) + 1
        return index


def build_index(pages: dict[str, str]) -> Index:
    """Build an :class:`Index` from a ``{url: html}`` mapping."""
    index = Index()
    for url, html in pages.items():
        index.add_document(url, html)
    return index
