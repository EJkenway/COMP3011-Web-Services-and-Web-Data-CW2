"""Unit tests for the crawler module.

All tests use ``requests-mock`` to intercept HTTP traffic - no real network
is ever touched. Politeness windows are set to 0 in most tests so the suite
runs in a fraction of a second; the politeness logic itself is validated in
two dedicated tests that monkeypatch ``time.sleep`` and inspect the calls.

requests-mock defaults to ``Content-Type: text/plain`` when ``text=`` is
used, but the crawler only accepts HTML responses. The ``HTML_HEADERS``
constant below is therefore passed to every HTML mock so the response
header matches what a real web server would send.
"""
import requests

from src.crawler import Crawler, _normalise_url, _same_domain


HTML_HEADERS = {"Content-Type": "text/html"}


# --- _normalise_url --------------------------------------------------------


def test_normalise_url_drops_fragment():
    assert (
        _normalise_url("https://example.com/page#section")
        == "https://example.com/page"
    )


def test_normalise_url_leaves_unchanged_when_no_fragment():
    assert _normalise_url("https://example.com/page") == "https://example.com/page"


def test_normalise_url_preserves_query_string():
    assert (
        _normalise_url("https://example.com/page?id=1#x")
        == "https://example.com/page?id=1"
    )


# --- _same_domain ----------------------------------------------------------


def test_same_domain_true_for_identical_host():
    assert _same_domain("https://example.com/a", "https://example.com/b") is True


def test_same_domain_false_for_different_host():
    assert _same_domain("https://example.com/a", "https://other.com/b") is False


def test_same_domain_distinguishes_subdomains():
    assert _same_domain("https://sub.example.com/", "https://example.com/") is False


# --- Crawler.crawl basics --------------------------------------------------


def test_crawl_returns_url_to_html_dict(requests_mock):
    requests_mock.get(
        "https://example.com/",
        text="<html><body>hello</body></html>",
        headers=HTML_HEADERS,
    )
    pages = Crawler(
        "https://example.com/", politeness_seconds=0, verbose=False
    ).crawl()
    assert pages == {"https://example.com/": "<html><body>hello</body></html>"}


def test_crawl_follows_links_breadth_first(requests_mock):
    requests_mock.get(
        "https://example.com/",
        text='<a href="/a">a</a><a href="/b">b</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get(
        "https://example.com/a", text="<p>page a</p>", headers=HTML_HEADERS
    )
    requests_mock.get(
        "https://example.com/b", text="<p>page b</p>", headers=HTML_HEADERS
    )
    pages = Crawler(
        "https://example.com/", politeness_seconds=0, verbose=False
    ).crawl()
    assert set(pages) == {
        "https://example.com/",
        "https://example.com/a",
        "https://example.com/b",
    }


def test_crawl_skips_off_domain_links(requests_mock):
    """External links must not be added to the frontier."""
    requests_mock.get(
        "https://example.com/",
        text='<a href="https://other.com/x">external</a>'
        '<a href="/local">local</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get(
        "https://example.com/local", text="<p>local</p>", headers=HTML_HEADERS
    )
    pages = Crawler(
        "https://example.com/", politeness_seconds=0, verbose=False
    ).crawl()
    assert "https://example.com/local" in pages
    assert "https://other.com/x" not in pages


def test_crawl_deduplicates_already_visited_urls(requests_mock):
    """A cycle A -> B -> A must not refetch or loop forever."""
    requests_mock.get(
        "https://example.com/",
        text='<a href="/b">b</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get(
        "https://example.com/b",
        text='<a href="/">back to root</a>',
        headers=HTML_HEADERS,
    )
    Crawler("https://example.com/", politeness_seconds=0, verbose=False).crawl()
    # Each unique URL fetched exactly once.
    assert requests_mock.call_count == 2


def test_crawl_treats_fragment_variants_as_one_page(requests_mock):
    """``/page`` and ``/page#anchor`` must be fetched only once."""
    requests_mock.get(
        "https://example.com/",
        text='<a href="/page">x</a><a href="/page#section">y</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get(
        "https://example.com/page", text="<p>page</p>", headers=HTML_HEADERS
    )
    Crawler("https://example.com/", politeness_seconds=0, verbose=False).crawl()
    # Root + /page = 2 unique fetches
    assert requests_mock.call_count == 2


# --- Crawler error handling -----------------------------------------------


def test_crawl_skips_404_responses(requests_mock):
    requests_mock.get(
        "https://example.com/",
        text='<a href="/missing">m</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get("https://example.com/missing", status_code=404)
    pages = Crawler(
        "https://example.com/", politeness_seconds=0, verbose=False
    ).crawl()
    assert "https://example.com/" in pages
    assert "https://example.com/missing" not in pages


def test_crawl_handles_network_exception_gracefully(requests_mock):
    """A ConnectionError on one page must not abort the whole crawl."""
    requests_mock.get(
        "https://example.com/",
        text='<a href="/broken">x</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get("https://example.com/broken", exc=requests.ConnectionError)
    pages = Crawler(
        "https://example.com/", politeness_seconds=0, verbose=False
    ).crawl()
    assert "https://example.com/" in pages
    assert "https://example.com/broken" not in pages


def test_crawl_skips_non_html_content(requests_mock):
    """Resources whose Content-Type is not HTML must be ignored."""
    requests_mock.get(
        "https://example.com/",
        text='<a href="/image.jpg">img</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get(
        "https://example.com/image.jpg",
        content=b"\xff\xd8\xff",
        headers={"Content-Type": "image/jpeg"},
    )
    pages = Crawler(
        "https://example.com/", politeness_seconds=0, verbose=False
    ).crawl()
    assert "https://example.com/image.jpg" not in pages


# --- Crawler limits and headers -------------------------------------------


def test_crawl_respects_max_pages_limit(requests_mock):
    requests_mock.get(
        "https://example.com/",
        text='<a href="/a">a</a><a href="/b">b</a><a href="/c">c</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get("https://example.com/a", text="a", headers=HTML_HEADERS)
    requests_mock.get("https://example.com/b", text="b", headers=HTML_HEADERS)
    requests_mock.get("https://example.com/c", text="c", headers=HTML_HEADERS)
    pages = Crawler(
        "https://example.com/",
        politeness_seconds=0,
        max_pages=2,
        verbose=False,
    ).crawl()
    assert len(pages) == 2


def test_crawl_sends_configured_user_agent_header(requests_mock):
    requests_mock.get("https://example.com/", text="ok", headers=HTML_HEADERS)
    Crawler(
        "https://example.com/",
        politeness_seconds=0,
        user_agent="MyTestBot/1.0",
        verbose=False,
    ).crawl()
    assert requests_mock.last_request.headers["User-Agent"] == "MyTestBot/1.0"


# --- Politeness window ----------------------------------------------------


def test_no_sleep_before_the_very_first_request(requests_mock, monkeypatch):
    """The first fetch must not be delayed - the timer starts at zero."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("src.crawler.time.sleep", lambda s: sleep_calls.append(s))
    requests_mock.get("https://example.com/", text="ok", headers=HTML_HEADERS)
    Crawler("https://example.com/", politeness_seconds=2.0, verbose=False).crawl()
    # Only one page, no link-out, so no sleep should ever be needed.
    assert sleep_calls == []


def test_verbose_mode_prints_progress(requests_mock, capsys):
    """When ``verbose=True`` (default for CLI usage), progress is printed."""
    requests_mock.get("https://example.com/", text="ok", headers=HTML_HEADERS)
    Crawler("https://example.com/", politeness_seconds=0, verbose=True).crawl()
    out = capsys.readouterr().out
    # The progress format is ``[N/M] fetching URL`` plus a finished summary line.
    assert "fetching" in out
    assert "Crawl finished" in out


def test_politeness_window_sleeps_between_requests(requests_mock, monkeypatch):
    """Between successive fetches, the crawler must wait the configured time."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("src.crawler.time.sleep", lambda s: sleep_calls.append(s))
    requests_mock.get(
        "https://example.com/",
        text='<a href="/b">b</a>',
        headers=HTML_HEADERS,
    )
    requests_mock.get("https://example.com/b", text="ok", headers=HTML_HEADERS)
    Crawler("https://example.com/", politeness_seconds=2.0, verbose=False).crawl()
    # Exactly one inter-request sleep, very close to 2.0 seconds.
    assert len(sleep_calls) == 1
    assert 1.5 < sleep_calls[0] <= 2.0
