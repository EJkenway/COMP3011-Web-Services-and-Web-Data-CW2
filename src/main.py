"""Command-line interface for the COMP3011 CW2 search engine tool.

Wires the crawler, indexer, and search modules into an interactive REPL with
the four assignment-mandated commands (build, load, print, find) plus
help/exit. The currently loaded :class:`Index` is held in a local variable
inside :func:`repl` and replaced when ``build`` or ``load`` succeeds.
"""
from __future__ import annotations

from pathlib import Path

from .crawler import Crawler
from .indexer import Index, build_index
from .search import find as search_find
from .search import print_term


PROMPT = "> "

# The single target site for this coursework.
ROOT_URL = "https://quotes.toscrape.com/"

# Resolve the index path relative to the project root (app/), so the tool
# behaves the same regardless of the user's current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "data" / "index.json"

HELP_TEXT = """\
Available commands:
  build              Crawl the website and build the inverted index.
  load               Load a previously built index from disk.
  print <word>       Print the inverted-index entry for <word>.
  find <words...>    Find pages containing all the given words.
  help               Show this message.
  exit               Quit the program.\
"""


def handle_build() -> Index | None:
    """Crawl the target site, build the index, save it. Return the new index."""
    print(f"Crawling {ROOT_URL}")
    print("(this may take several minutes due to the 6-second politeness window)")
    pages = Crawler(ROOT_URL).crawl()
    if not pages:
        print("Crawl returned no pages; index not built.")
        return None

    print(f"Building index from {len(pages)} pages ...")
    index = build_index(pages)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    index.save(INDEX_PATH)
    print(
        f"Index built: {index.num_documents} documents, "
        f"{index.vocabulary_size} unique terms."
    )
    print(f"Saved to {INDEX_PATH}")
    return index


def handle_load() -> Index | None:
    """Load the index file from disk, or print an error and return None."""
    if not INDEX_PATH.exists():
        print(f"No index found at {INDEX_PATH}. Run 'build' first.")
        return None
    try:
        index = Index.load(INDEX_PATH)
    except (OSError, ValueError) as exc:
        print(f"Failed to load index: {exc}")
        return None
    print(
        f"Loaded index: {index.num_documents} documents, "
        f"{index.vocabulary_size} unique terms."
    )
    return index


def _require_index(index: Index | None) -> bool:
    """Guard for read-only commands: print a hint if no index is loaded."""
    if index is None:
        print("No index loaded. Run 'build' or 'load' first.")
        return False
    return True


def handle_print(index: Index | None, args: list[str]) -> None:
    if not args:
        print("usage: print <word>")
        return
    if len(args) > 1:
        extras = " ".join(args[1:])
        print(f"warning: 'print' takes one word; ignoring: {extras}")
    if not _require_index(index):
        return
    print_term(index, args[0])


def handle_find(index: Index | None, args: list[str]) -> None:
    if not args:
        print("usage: find <word> [<word> ...]")
        return
    if not _require_index(index):
        return
    results = search_find(index, args)
    if not results:
        print("No pages match.")
        return
    print(f"{len(results)} page(s) match:")
    for url in results:
        print(f"  {url}")


def repl() -> None:
    """Run the interactive read-eval-print loop until EOF or 'exit'."""
    print("Search Engine Tool - type 'help' for commands, 'exit' to quit.")
    index: Index | None = None

    while True:
        try:
            line = input(PROMPT)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        tokens = line.strip().split()
        if not tokens:
            continue

        command, *args = tokens
        command = command.lower()

        if command == "exit":
            break
        elif command == "help":
            print(HELP_TEXT)
        elif command == "build":
            new_index = handle_build()
            if new_index is not None:
                index = new_index
        elif command == "load":
            new_index = handle_load()
            if new_index is not None:
                index = new_index
        elif command == "print":
            handle_print(index, args)
        elif command == "find":
            handle_find(index, args)
        else:
            print(
                f"unknown command: {command!r} "
                "(type 'help' for available commands)"
            )


if __name__ == "__main__":
    repl()
