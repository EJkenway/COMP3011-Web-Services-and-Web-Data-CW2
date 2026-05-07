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


def test_find_returns_empty_when_no_document_contains_all_terms():
    """All terms exist in the index, but no single document contains all of them.

    Distinct from the missing-term short-circuit above: here every query term
    is found, but the intersection of their posting sets is empty. This
    exercises the path where AND filtering eliminates all candidates before
    TF-IDF scoring runs.
    """
    # In _make_index: 'quick' is only in doc 1, 'lazy' is only in doc 2.
    assert find(_make_index(), ["quick", "lazy"]) == []


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


def test_find_ties_are_broken_by_ascending_doc_id():
    """Documents with equal TF-IDF scores must be returned in doc_id order."""
    # In _make_index(), 'fox' has tf=1 in both doc 1 and doc 2 -> equal scores.
    # Tie-break by doc_id means doc 1 (URL a) comes before doc 2 (URL b).
    results = find(_make_index(), ["fox"])
    assert results[0] == "https://example.com/a"
    assert results[1] == "https://example.com/b"


def test_find_ranks_higher_term_frequency_first():
    """A document with higher tf for the query term must rank ahead of one with lower tf."""
    index = Index()
    # doc 1: 'fox' once
    index.add_document("https://example.com/a", "<p>quick brown fox</p>")
    # doc 2: 'fox' three times -> higher tf -> should rank first
    index.add_document("https://example.com/b", "<p>fox fox fox jumps</p>")
    # doc 3: no 'fox', just to give N a non-trivial value
    index.add_document("https://example.com/c", "<p>cat dog bird</p>")

    results = find(index, ["fox"])
    assert results == ["https://example.com/b", "https://example.com/a"]


def test_find_weights_rare_terms_more_heavily_via_idf():
    """A rarer query term contributes more to the score than a common one."""
    index = Index()
    # 'common' appears in every doc; 'rare' appears in only one.
    index.add_document("https://example.com/a", "<p>common common common</p>")
    index.add_document("https://example.com/b", "<p>common common</p>")
    index.add_document("https://example.com/c", "<p>common rare</p>")

    # find('common rare') matches only doc c (AND filter).
    # This single-doc result is trivial; the real assertion is on a query
    # where two candidates compete and idf decides.
    index2 = Index()
    index2.add_document("https://example.com/a", "<p>common common common rare</p>")
    index2.add_document("https://example.com/b", "<p>common common common common</p>")
    index2.add_document("https://example.com/c", "<p>common common common common</p>")

    # Query 'common rare':
    #   - doc a contains both -> matches
    #   - doc b, c contain only 'common' -> filtered out by AND
    # Single match - the real point of this test is below.
    results = find(index2, ["common", "rare"])
    assert results == ["https://example.com/a"]

    # Now construct a case where two docs both contain a rare and a common term,
    # but with different proportions. Higher rare-term tf should win.
    index3 = Index()
    # doc a: 'common' three times, 'rare' once
    index3.add_document("https://example.com/a", "<p>common common common rare</p>")
    # doc b: 'common' once, 'rare' three times -> rare-heavy -> higher score
    index3.add_document("https://example.com/b", "<p>common rare rare rare</p>")
    # doc c: only 'common' to inflate doc_freq for 'common' -> idf(common) low
    index3.add_document("https://example.com/c", "<p>common common</p>")

    results = find(index3, ["common", "rare"])
    # doc b has more occurrences of the rare (high-idf) term -> ranks first.
    assert results == ["https://example.com/b", "https://example.com/a"]


def test_find_tokenises_multi_word_single_argument():
    """A single arg containing whitespace tokenises into multiple AND terms."""
    results = find(_make_index(), ["brown fox"])
    assert results == ["https://example.com/a", "https://example.com/b"]


def test_find_on_empty_index_returns_empty():
    empty = Index()
    assert find(empty, ["fox"]) == []
    assert find(empty, ["brown", "fox"]) == []
