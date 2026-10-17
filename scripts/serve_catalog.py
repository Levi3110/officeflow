"""Serve the same fictional catalog for a manual human-baseline task. Sends no desktop input."""

import argparse
from threading import Event

from synthetic_human.fixture import Catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        with Catalog(args.port) as catalog:
            print(
                f"Baseline catalog: {catalog.url}\nKeep this terminal open; Ctrl+C stops the server.",
                flush=True,
            )
            Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
