"""Unit tests for the search module.

Builds a small deterministic :class:`Index` from synthetic HTML and exercises
both ``print_term`` (output captured via the pytest ``capsys`` fixture) and
``find`` (return-value assertions). No real network, no real index file.
"""
from src.indexer import Index
from src.search import find, print_term


def _make_index() -> Index:
    """Three-document fixture used by most tests in this module.

    Doc 1: 'the quick brown fox'
    Doc 2: 'the lazy dog and the brown fox'
    Doc 3: 'nothing about animals'
    """
    index = Index()
    index.add_document("https://example.com/a", "<p>the quick brown fox</p>")
    index.add_document(
        "https://example.com/b", "<p>the lazy dog and the brown fox</p>"
    )
    index.add_document("https://example.com/c", "<p>nothing about animals</p>")
    return index


# --- print_term -----------------------------------------------------------


def test_print_term_existing_word_shows_doc_freq_and_postings(capsys):
    print_term(_make_index(), "fox")
    out = capsys.readouterr().out
    assert "Term: fox" in out
    assert "Document frequency: 2" in out
    assert "https://example.com/a" in out
    assert "https://example.com/b" in out


def test_print_term_missing_word_prints_friendly_message(capsys):
    print_term(_make_index(), "unicorn")
    out = capsys.readouterr().out
    assert "not in the index" in out


def test_print_term_is_case_insensitive(capsys):
    print_term(_make_index(), "FOX")
    out = capsys.readouterr().out
    assert "Term: fox" in out
    assert "Document frequency: 2" in out


def test_print_term_truncates_long_position_lists(capsys):
    """For >10 positions in one doc, output should show '... (N total)'."""
    index = Index()
    index.add_document("u", "<p>" + " ".join(["word"] * 20) + "</p>")
    print_term(index, "word")
    out = capsys.readouterr().out
    assert "..." in out
    assert "20 total" in out


def test_print_term_shows_all_positions_when_under_cap(capsys):
    """For <=10 positions, output should not contain the truncation marker."""
    index = Index()
    index.add_document("u", "<p>word and word and word</p>")  # 3 occurrences
    print_term(index, "word")
    out = capsys.readouterr().out
    assert "total" not in out


# --- find -----------------------------------------------------------------


def test_find_single_word_returns_matching_pages():
    results = find(_make_index(), ["fox"])
    assert results == ["https://example.com/a", "https://example.com/b"]


def test_find_word_not_in_index_returns_empty():
    assert find(_make_index(), ["unicorn"]) == []


def test_find_two_words_returns_intersection():
    """'brown fox' must return only docs containing BOTH words."""
    results = find(_make_index(), ["brown", "fox"])
    assert results == ["https://example.com/a", "https://example.com/b"]


def test_find_one_missing_term_short_circuits_to_empty():
    """AND semantics: a single missing term yields no results."""
    assert find(_make_index(), ["brown", "unicorn"]) == []


def test_find_returns_only_documents_containing_every_word():
    """'lazy' is in doc 2 only -> 'brown lazy' returns just doc 2."""
    results = find(_make_index(), ["brown", "lazy"])
    assert results == ["https://example.com/b"]


def test_find_is_case_insensitive():
    results = find(_make_index(), ["BROWN", "Fox"])
    assert results == ["https://example.com/a", "https://example.com/b"]


def test_find_strips_punctuation_from_query():
    """'fox?' must match indexed term 'fox'."""
    results = find(_make_index(), ["fox?"])
    assert results == ["https://example.com/a", "https://example.com/b"]


def test_find_with_empty_query_returns_empty():
    assert find(_make_index(), []) == []


def test_find_with_punctuation_only_query_returns_empty():
    """A query that tokenises to no terms must return empty."""
    assert find(_make_index(), ["!?.,"]) == []


def test_find_results_are_sorted_by_doc_id():
    """Order is determined by insertion order (doc_id), not by URL."""
    results = find(_make_index(), ["fox"])
    assert results[0] == "https://example.com/a"
    assert results[1] == "https://example.com/b"


def test_find_tokenises_multi_word_single_argument():
    """A single arg containing whitespace tokenises into multiple AND terms."""
    results = find(_make_index(), ["brown fox"])
    assert results == ["https://example.com/a", "https://example.com/b"]


def test_find_on_empty_index_returns_empty():
    empty = Index()
    assert find(empty, ["fox"]) == []
    assert find(empty, ["brown", "fox"]) == []
