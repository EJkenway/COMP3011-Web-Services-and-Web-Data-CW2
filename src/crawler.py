"""Crawler module for the search engine tool.

Performs a polite breadth-first crawl of a website, restricted to URLs on the
same domain as the seed. Respects a configurable politeness window between
requests (default 6 s, as required by the coursework brief) and handles
transient HTTP/network errors gracefully.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


USER_AGENT = "COMP3011-CW2-SearchEngineBot/1.0 (educational; Leeds COMP3011)"
DEFAULT_POLITENESS_SECONDS = 6.0
DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_PAGES = 200


def _normalise_url(url: str) -> str:
    """Drop the fragment so URLs differing only by '#anchor' are treated as one."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def _same_domain(url: str, root: str) -> bool:
    return urlparse(url).netloc == urlparse(root).netloc


class Crawler:
    """Polite breadth-first crawler restricted to a single domain.

    The politeness window enforces a minimum delay between successive HTTP
    requests, regardless of how fast the network responds. This keeps the tool
    compliant with the coursework's 6-second requirement and avoids triggering
    rate-limiting on the target server.
    """

    def __init__(
        self,
        root_url: str,
        *,
        politeness_seconds: float = DEFAULT_POLITENESS_SECONDS,
        timeout: float = DEFAULT_TIMEOUT,
        max_pages: int = DEFAULT_MAX_PAGES,
        user_agent: str = USER_AGENT,
        verbose: bool = True,
    ) -> None:
        self.root_url = _normalise_url(root_url)
        self.politeness_seconds = politeness_seconds
        self.timeout = timeout
        self.max_pages = max_pages
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_at: float = 0.0

    def _wait_for_politeness(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.politeness_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _fetch(self, url: str) -> str | None:
        """Fetch one page; return HTML text or None if the page is unusable."""
        self._wait_for_politeness()
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            self._last_request_at = time.monotonic()
            self._log(f"  ! request failed for {url}: {exc}")
            return None
        self._last_request_at = time.monotonic()

        if response.status_code != 200:
            self._log(f"  ! HTTP {response.status_code} for {url}")
            return None
        if "html" not in response.headers.get("Content-Type", "").lower():
            self._log(f"  ! non-HTML content at {url}")
            return None
        return response.text

    def _extract_links(self, html: str, base_url: str) -> Iterable[str]:
        """Yield absolute, same-domain URLs found in <a href="..."> tags."""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("a", href=True):
            absolute = _normalise_url(urljoin(base_url, tag["href"]))
            if _same_domain(absolute, self.root_url):
                yield absolute

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

    def crawl(self) -> dict[str, str]:
        """Run BFS crawl from ``root_url``; return mapping of URL to HTML text."""
        pages: dict[str, str] = {}
        seen: set[str] = {self.root_url}
        frontier: deque[str] = deque([self.root_url])

        while frontier and len(pages) < self.max_pages:
            url = frontier.popleft()
            self._log(f"[{len(pages) + 1}/{self.max_pages}] fetching {url}")
            html = self._fetch(url)
            if html is None:
                continue
            pages[url] = html
            for link in self._extract_links(html, url):
                if link not in seen:
                    seen.add(link)
                    frontier.append(link)
        self._log(f"Crawl finished: {len(pages)} pages collected.")
        return pages
