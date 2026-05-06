"""Unit tests for the tokeniser module.

Covers both ``extract_text`` (HTML stripping) and ``tokenise`` (lowercase
alphanumeric splitting), plus an end-to-end pipeline check using a fragment
of synthetic HTML in the same shape as a quotes.toscrape.com page.
"""
from src.tokeniser import extract_text, tokenise


# --- extract_text ----------------------------------------------------------


def test_extract_text_returns_visible_content():
    html = "<html><body><p>Hello world</p></body></html>"
    assert "Hello world" in extract_text(html)


def test_extract_text_removes_script_tags():
    html = '<html><body><p>visible</p><script>alert("hi")</script></body></html>'
    text = extract_text(html)
    assert "visible" in text
    assert "alert" not in text


def test_extract_text_removes_style_tags():
    html = "<html><body><style>body { color: red; }</style><p>shown</p></body></html>"
    text = extract_text(html)
    assert "shown" in text
    assert "color" not in text
    assert "red" not in text


def test_extract_text_handles_empty_input():
    assert extract_text("") == ""


def test_extract_text_handles_no_tags():
    assert "plain text" in extract_text("plain text")


def test_extract_text_inserts_separator_between_adjacent_tags():
    """Adjacent tags must not have their text concatenated into a single word."""
    html = "<p>foo</p><p>bar</p>"
    tokens = tokenise(extract_text(html))
    assert "foo" in tokens
    assert "bar" in tokens
    assert "foobar" not in tokens


# --- tokenise --------------------------------------------------------------


def test_tokenise_lowercases_input():
    assert tokenise("Hello WORLD") == ["hello", "world"]


def test_tokenise_strips_punctuation():
    assert tokenise("Hello, world!") == ["hello", "world"]


def test_tokenise_handles_empty_string():
    assert tokenise("") == []


def test_tokenise_handles_punctuation_only():
    assert tokenise("!?.,;:") == []


def test_tokenise_preserves_token_order():
    assert tokenise("one two three four") == ["one", "two", "three", "four"]


def test_tokenise_treats_digits_as_tokens():
    assert tokenise("Python 3.12") == ["python", "3", "12"]


def test_tokenise_splits_contractions_at_apostrophe():
    """Documented behaviour: apostrophes split tokens (don't -> don, t).

    This is the trade-off accepted by the simple ``[a-z0-9]+`` regex; it is
    discussed in the tokeniser module docstring and the demo video.
    """
    assert tokenise("don't") == ["don", "t"]


def test_tokenise_collapses_multiple_whitespace():
    assert tokenise("foo    bar\n\nbaz\tqux") == ["foo", "bar", "baz", "qux"]


# --- end-to-end pipeline ---------------------------------------------------


def test_pipeline_extracts_then_tokenises_a_quote_page():
    """End-to-end check using a quotes.toscrape.com-shaped HTML fragment."""
    html = """
    <html>
      <head>
        <title>Quotes to Scrape</title>
        <script>console.log("ignored");</script>
        <style>body { font-size: 14px; }</style>
      </head>
      <body>
        <h1>Tropical Fish</h1>
        <p>The clownfish is a saltwater fish.</p>
      </body>
    </html>
    """
    tokens = tokenise(extract_text(html))
    # Visible text should be tokenised
    assert "tropical" in tokens
    assert "fish" in tokens
    assert "clownfish" in tokens
    assert "saltwater" in tokens
    # Script / style content must NOT leak into the index
    assert "console" not in tokens
    assert "ignored" not in tokens
    assert "font" not in tokens
