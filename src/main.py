"""Command-line interface for the COMP3011 CW2 search engine tool.

Implements an interactive REPL with the four assignment-mandated commands
(build, load, print, find) plus help/exit. Each command currently prints a
"not yet implemented" placeholder; subsequent commits wire them to the
crawler, indexer, and search modules.
"""

PROMPT = "> "

HELP_TEXT = """\
Available commands:
  build              Crawl the website and build the inverted index.
  load               Load a previously built index from disk.
  print <word>       Print the inverted-index entry for <word>.
  find <words...>    Find pages containing the given word(s).
  help               Show this message.
  exit               Quit the program.\
"""


def dispatch(command: str, args: list[str]) -> None:
    """Route a parsed command to its (currently stub) handler."""
    if command == "build":
        print("[build] not yet implemented")
    elif command == "load":
        print("[load] not yet implemented")
    elif command == "print":
        if not args:
            print("usage: print <word>")
            return
        print(f"[print {args[0]}] not yet implemented")
    elif command == "find":
        if not args:
            print("usage: find <word> [<word> ...]")
            return
        print(f"[find {' '.join(args)}] not yet implemented")
    elif command == "help":
        print(HELP_TEXT)
    else:
        print(f"unknown command: {command!r} (type 'help' for available commands)")


def repl() -> None:
    """Run the interactive read-eval-print loop until EOF or 'exit'."""
    print("Search Engine Tool - type 'help' for commands, 'exit' to quit.")
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

        dispatch(command, args)


if __name__ == "__main__":
    repl()
