"""Unit tests for the main CLI module.

Three groups of tests:

  * handler tests        - call ``handle_build`` / ``handle_load`` /
    ``handle_print`` / ``handle_find`` directly. The index path and the
    Crawler class are monkeypatched, so no real network or real file at
    ``data/index.json`` is touched.

  * ``_require_index``    - small guard helper.

  * REPL tests           - feed scripted lines into the loop via a
    monkeypatched ``input()`` and verify the dispatched behaviour from
    captured stdout.
"""
import pytest

from src import main as main_mod
from src.indexer import Index


# --- Fixtures -------------------------------------------------------------


@pytest.fixture
def populated_index() -> Index:
    """A small Index used by handler-level tests."""
    index = Index()
    index.add_document("https://example.com/a", "<p>the quick brown fox</p>")
    index.add_document(
        "https://example.com/b", "<p>the lazy dog and the brown fox</p>"
    )
    index.add_document("https://example.com/c", "<p>nothing about animals</p>")
    return index


@pytest.fixture
def temp_index_path(tmp_path, monkeypatch):
    """Redirect ``main.INDEX_PATH`` to a temporary file for one test."""
    path = tmp_path / "index.json"
    monkeypatch.setattr(main_mod, "INDEX_PATH", path)
    return path


def _scripted_input(lines):
    """Return a fake ``input`` that yields each line, then raises EOFError."""
    queue = list(lines)

    def fake_input(_prompt=""):
        if not queue:
            raise EOFError
        return queue.pop(0)

    return fake_input


def _fake_crawler_factory(pages):
    """Build a stand-in Crawler class whose ``crawl`` returns ``pages``."""

    class FakeCrawler:
        def __init__(self, *_args, **_kwargs):
            pass

        def crawl(self):
            return pages

    return FakeCrawler


# --- _require_index -------------------------------------------------------


def test_require_index_returns_true_when_index_present(populated_index, capsys):
    assert main_mod._require_index(populated_index) is True
    assert capsys.readouterr().out == ""


def test_require_index_returns_false_and_prints_hint_when_none(capsys):
    assert main_mod._require_index(None) is False
    assert "No index loaded" in capsys.readouterr().out


# --- handle_print ---------------------------------------------------------


def test_handle_print_with_no_args_prints_usage(populated_index, capsys):
    main_mod.handle_print(populated_index, [])
    assert "usage: print <word>" in capsys.readouterr().out


def test_handle_print_with_no_index_prints_load_hint(capsys):
    main_mod.handle_print(None, ["fox"])
    assert "No index loaded" in capsys.readouterr().out


def test_handle_print_with_index_shows_term_entry(populated_index, capsys):
    main_mod.handle_print(populated_index, ["fox"])
    out = capsys.readouterr().out
    assert "Term: fox" in out
    assert "Document frequency: 2" in out


# --- handle_find ----------------------------------------------------------


def test_handle_find_with_no_args_prints_usage(populated_index, capsys):
    main_mod.handle_find(populated_index, [])
    assert "usage: find" in capsys.readouterr().out


def test_handle_find_with_no_index_prints_load_hint(capsys):
    main_mod.handle_find(None, ["fox"])
    assert "No index loaded" in capsys.readouterr().out


def test_handle_find_prints_matching_urls(populated_index, capsys):
    main_mod.handle_find(populated_index, ["brown", "fox"])
    out = capsys.readouterr().out
    assert "page(s) match" in out
    assert "https://example.com/a" in out
    assert "https://example.com/b" in out


def test_handle_find_prints_no_match_for_missing_term(populated_index, capsys):
    main_mod.handle_find(populated_index, ["unicorn"])
    assert "No pages match" in capsys.readouterr().out


# --- handle_load ----------------------------------------------------------


def test_handle_load_returns_none_when_file_missing(temp_index_path, capsys):
    """``temp_index_path`` is created by the fixture but the file doesn't exist."""
    assert main_mod.handle_load() is None
    assert "No index found at" in capsys.readouterr().out


def test_handle_load_returns_none_for_malformed_json(temp_index_path, capsys):
    temp_index_path.write_text("not json", encoding="utf-8")
    assert main_mod.handle_load() is None
    assert "Failed to load" in capsys.readouterr().out


def test_handle_load_returns_index_for_valid_file(
    populated_index, temp_index_path, capsys
):
    populated_index.save(temp_index_path)
    loaded = main_mod.handle_load()
    assert loaded is not None
    assert loaded.num_documents == 3
    assert "Loaded index" in capsys.readouterr().out


# --- handle_build (Crawler stubbed) ---------------------------------------


def test_handle_build_returns_none_when_crawler_finds_nothing(
    monkeypatch, temp_index_path, capsys
):
    """If the crawler yields zero pages, no index file is written."""
    monkeypatch.setattr("src.main.Crawler", _fake_crawler_factory({}))
    assert main_mod.handle_build() is None
    assert "Crawl returned no pages" in capsys.readouterr().out
    assert not temp_index_path.exists()


def test_handle_build_writes_index_when_crawler_succeeds(
    monkeypatch, temp_index_path, capsys
):
    fake_pages = {
        "https://example.com/a": "<p>the quick brown fox</p>",
        "https://example.com/b": "<p>the lazy dog and the brown fox</p>",
    }
    monkeypatch.setattr("src.main.Crawler", _fake_crawler_factory(fake_pages))
    result = main_mod.handle_build()
    assert result is not None
    assert result.num_documents == 2
    assert temp_index_path.exists()
    out = capsys.readouterr().out
    assert "2 documents" in out
    assert "Saved to" in out


# --- repl loop ------------------------------------------------------------


def test_repl_prints_welcome_banner_then_exits_on_eof(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", _scripted_input([]))
    main_mod.repl()
    assert "Search Engine Tool" in capsys.readouterr().out


def test_repl_silently_ignores_blank_lines(monkeypatch, capsys):
    monkeypatch.setattr(
        "builtins.input", _scripted_input(["", "  ", "exit"])
    )
    main_mod.repl()
    assert "unknown command" not in capsys.readouterr().out


def test_repl_help_prints_command_list(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", _scripted_input(["help", "exit"]))
    main_mod.repl()
    out = capsys.readouterr().out
    assert "Available commands" in out
    for cmd in ("build", "load", "print", "find"):
        assert cmd in out


def test_repl_unknown_command_shows_friendly_error(monkeypatch, capsys):
    monkeypatch.setattr(
        "builtins.input", _scripted_input(["nonsense", "exit"])
    )
    main_mod.repl()
    assert "unknown command" in capsys.readouterr().out


def test_repl_keyboard_interrupt_does_not_exit_loop(monkeypatch, capsys):
    """Ctrl+C aborts the current input but the REPL keeps going."""
    actions = iter([KeyboardInterrupt, "help", "exit"])

    def fake_input(_prompt=""):
        action = next(actions)
        if action is KeyboardInterrupt:
            raise KeyboardInterrupt
        return action

    monkeypatch.setattr("builtins.input", fake_input)
    main_mod.repl()
    # If the loop had exited on Ctrl+C, "help" would never have been processed.
    assert "Available commands" in capsys.readouterr().out


def test_repl_print_without_index_prints_load_hint(monkeypatch, capsys):
    monkeypatch.setattr(
        "builtins.input", _scripted_input(["print fox", "exit"])
    )
    main_mod.repl()
    assert "No index loaded" in capsys.readouterr().out


def test_repl_load_then_find_uses_loaded_index(
    populated_index, temp_index_path, monkeypatch, capsys
):
    """After load, a subsequent find call uses the in-memory index."""
    populated_index.save(temp_index_path)
    monkeypatch.setattr(
        "builtins.input",
        _scripted_input(["load", "find brown fox", "exit"]),
    )
    main_mod.repl()
    out = capsys.readouterr().out
    assert "Loaded index" in out
    assert "https://example.com/a" in out


def test_repl_build_then_print_uses_built_index(
    monkeypatch, temp_index_path, capsys
):
    """build leaves the index in memory; the next print sees it."""
    fake_pages = {"https://example.com/a": "<p>brown fox</p>"}
    monkeypatch.setattr("src.main.Crawler", _fake_crawler_factory(fake_pages))
    monkeypatch.setattr(
        "builtins.input",
        _scripted_input(["build", "print fox", "exit"]),
    )
    main_mod.repl()
    out = capsys.readouterr().out
    assert "1 documents" in out  # printed by handle_build
    assert "Term: fox" in out  # printed by handle_print
