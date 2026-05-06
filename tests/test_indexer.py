"""Unit tests for the indexer module.

Exercises the :class:`Index` API in isolation - no real network is touched
because every test feeds synthetic HTML strings directly into
``add_document`` or ``build_index``.
"""
import json

import pytest

from src.indexer import Index, build_index


# Synthetic HTML used across multiple tests. Kept short so failures are easy
# to read in pytest's diff output.
HTML_A = "<html><body><p>The quick brown fox.</p></body></html>"
HTML_B = "<html><body><p>The lazy dog and the brown fox.</p></body></html>"
HTML_C = "<html><body><p>Nothing about animals.</p></body></html>"


# --- Index initial state ---------------------------------------------------


def test_new_index_is_empty():
    index = Index()
    assert index.num_documents == 0
    assert index.vocabulary_size == 0


def test_new_index_contains_no_terms():
    index = Index()
    assert "anything" not in index
    assert index.get("anything") is None


# --- add_document basics --------------------------------------------------


def test_add_document_returns_sequential_doc_ids_starting_at_one():
    index = Index()
    assert index.add_document("u1", HTML_A) == 1
    assert index.add_document("u2", HTML_B) == 2
    assert index.add_document("u3", HTML_C) == 3


def test_add_document_registers_the_url_in_the_documents_table():
    index = Index()
    doc_id = index.add_document("https://example.com/a", HTML_A)
    assert index.documents[doc_id] == "https://example.com/a"


def test_add_document_records_term_frequency():
    index = Index()
    index.add_document("u", "<p>the brown fox runs and the brown fox jumps</p>")
    assert index.get("brown")["postings"][1]["tf"] == 2
    assert index.get("the")["postings"][1]["tf"] == 2
    assert index.get("runs")["postings"][1]["tf"] == 1


def test_add_document_records_token_positions_in_order():
    """Positions must reflect the 0-indexed token order in the page."""
    index = Index()
    # Tokens: ["the", "brown", "fox"]
    index.add_document("u", "<p>the brown fox</p>")
    assert index.get("the")["postings"][1]["positions"] == [0]
    assert index.get("brown")["postings"][1]["positions"] == [1]
    assert index.get("fox")["postings"][1]["positions"] == [2]


def test_add_document_increments_doc_freq_across_documents():
    index = Index()
    index.add_document("u1", HTML_A)  # 'fox' present
    index.add_document("u2", HTML_B)  # 'fox' present
    index.add_document("u3", HTML_C)  # 'fox' absent
    assert index.get("fox")["doc_freq"] == 2


def test_add_document_increments_num_documents_and_vocabulary_size():
    index = Index()
    index.add_document("u1", HTML_A)
    assert index.num_documents == 1
    vocab_after_first = index.vocabulary_size
    index.add_document("u2", HTML_B)
    assert index.num_documents == 2
    # Adding a doc with overlapping vocabulary should still grow it (new words: lazy, dog, and).
    assert index.vocabulary_size > vocab_after_first


# --- add_document edge cases ----------------------------------------------


def test_add_document_is_case_insensitive():
    """HTML with mixed-case words is indexed under lowercase keys."""
    index = Index()
    index.add_document("u", "<p>BROWN fox Brown FOX brown</p>")
    assert "brown" in index
    assert "BROWN" not in index
    assert index.get("brown")["postings"][1]["tf"] == 3


def test_add_document_strips_html_markup_before_indexing():
    """Words inside script/style tags must not enter the index."""
    index = Index()
    index.add_document("u", "<p>visible</p><script>scriptcontent</script>")
    assert "visible" in index
    assert "scriptcontent" not in index


def test_add_document_handles_html_with_no_visible_text():
    index = Index()
    doc_id = index.add_document("u", "<html><body></body></html>")
    assert index.documents[doc_id] == "u"
    assert index.vocabulary_size == 0


# --- save / load round-trip -----------------------------------------------


def test_save_writes_well_formed_json(tmp_path):
    index = Index()
    index.add_document("u", "<p>hello world</p>")
    path = tmp_path / "index.json"
    index.save(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {"documents", "terms"}
    # JSON cannot encode integer keys, so doc_ids are stringified on disk.
    assert payload["documents"]["1"] == "u"


def test_save_load_round_trip_preserves_index_contents(tmp_path):
    original = Index()
    original.add_document("u1", HTML_A)
    original.add_document("u2", HTML_B)
    original.add_document("u3", HTML_C)
    path = tmp_path / "index.json"
    original.save(path)

    loaded = Index.load(path)
    assert loaded.num_documents == original.num_documents
    assert loaded.vocabulary_size == original.vocabulary_size
    assert loaded.documents == original.documents
    assert loaded.get("brown") == original.get("brown")
    assert loaded.get("fox") == original.get("fox")


def test_load_restores_next_doc_id_so_subsequent_adds_continue(tmp_path):
    """A new document added after load must get the next sequential id."""
    first = Index()
    first.add_document("u1", HTML_A)
    first.add_document("u2", HTML_B)
    path = tmp_path / "index.json"
    first.save(path)

    loaded = Index.load(path)
    assert loaded.add_document("u3", HTML_C) == 3


def test_load_raises_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        Index.load(tmp_path / "does_not_exist.json")


def test_load_raises_on_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json at all{{{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        Index.load(path)


# --- build_index helper ---------------------------------------------------


def test_build_index_from_empty_pages_returns_empty_index():
    index = build_index({})
    assert index.num_documents == 0
    assert index.vocabulary_size == 0


def test_build_index_indexes_every_page():
    pages = {"u1": HTML_A, "u2": HTML_B, "u3": HTML_C}
    index = build_index(pages)
    assert index.num_documents == 3
    assert set(index.documents.values()) == {"u1", "u2", "u3"}


def test_build_index_then_save_load_round_trip(tmp_path):
    """End-to-end: crawler-like input -> build -> save -> load."""
    pages = {"u1": HTML_A, "u2": HTML_B, "u3": HTML_C}
    original = build_index(pages)
    path = tmp_path / "index.json"
    original.save(path)

    loaded = Index.load(path)
    assert loaded.num_documents == 3
    assert loaded.get("brown") == original.get("brown")
