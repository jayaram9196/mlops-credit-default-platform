"""CLI for the LLM/RAG layer.

Usage:
  python -m src.llm.cli build               # build the FAISS index
  python -m src.llm.cli search "deny utilisation"   # smoke retrieval
"""

from __future__ import annotations

import argparse
import sys

from src.llm.vectorstore import build_index, load_index
from src.utils import configure_logging, get_logger

log = get_logger(__name__)


def _build(_args) -> int:
    build_index()
    return 0


def _search(args) -> int:
    store = load_index()
    docs = store.similarity_search(args.query, k=args.k)
    for i, d in enumerate(docs, 1):
        print(f"[{i}] {d.metadata.get('policy_id')} {d.metadata.get('section')}")
        print(d.page_content[:240], "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="src.llm.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="(re)build the FAISS index over data/policies")

    s = sub.add_parser("search", help="retrieve top-k policy sections for a query")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=4)

    args = parser.parse_args(argv)
    handlers = {"build": _build, "search": _search}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
