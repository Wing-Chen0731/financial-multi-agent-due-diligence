from __future__ import annotations

import argparse
import json

from src.rag.service import build_vector_index, retrieve_context


def main() -> None:
    parser = argparse.ArgumentParser(description="金融知识库向量索引工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    index_parser = subparsers.add_parser("index", help="切片、Embedding 并持久化到 Chroma")
    index_parser.add_argument("--directory", default=None)
    index_parser.add_argument("--persist-dir", default=None)
    query_parser = subparsers.add_parser("query", help="查询已建立的向量库")
    query_parser.add_argument("text")
    query_parser.add_argument("--top-k", type=int, default=4)
    args = parser.parse_args()
    try:
        if args.command == "index":
            result = build_vector_index(args.directory, args.persist_dir)
        else:
            result = retrieve_context(args.text, top_k=args.top_k)
    except RuntimeError as exc:
        parser.exit(1, f"RAG error: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
