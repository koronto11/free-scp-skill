#!/usr/bin/env python3
"""
Search the local SCP vector index using natural language queries.
Supports both English (scp_items) and Chinese (scp_items_cn) collections.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows terminal encoding for CJK output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config_utils import get_config, get_data_dir


def contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def query_collection(client, collection_name: str, embedding, top_k: int):
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        return [], [], []
    if collection.count() == 0:
        return [], [], []
    results = collection.query(query_embeddings=[embedding], n_results=top_k)
    docs = results["documents"][0] if results.get("documents") else []
    metas = results["metadatas"][0] if results.get("metadatas") else []
    dists = results["distances"][0] if results.get("distances") else []
    return docs, metas, dists


def main():
    parser = argparse.ArgumentParser(description="Search local SCP index.")
    parser.add_argument("query", type=str, help="Natural language query.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return.")
    parser.add_argument("--collection", type=str, default="scp_items", help="Primary ChromaDB collection name.")
    parser.add_argument("--include-cn", action="store_true", help="Also search the Chinese branch collection.")
    args = parser.parse_args()

    cfg = get_config()
    vector_db_path = cfg["vector_db_path"]
    embedding_model = cfg["embedding_model"]

    if not Path(vector_db_path).exists():
        print("ERROR: Vector database not found. Please run 'python tools/init_db.py' first.")
        sys.exit(1)

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        print(f"ERROR: Missing dependency: {exc}. Run: pip install -r requirements.txt")
        sys.exit(1)

    client = chromadb.PersistentClient(path=vector_db_path)

    auto_include_cn = contains_chinese(args.query)
    include_cn = args.include_cn or auto_include_cn

    print(f"Encoding query: '{args.query}' ...")
    print(f"Using embedding model: {embedding_model}")
    if auto_include_cn and not args.include_cn:
        print("Detected Chinese characters: automatically including SCP-CN branch.")

    model = SentenceTransformer(embedding_model)
    embedding = model.encode(args.query).tolist()

    # Query primary (EN) collection
    en_docs, en_metas, en_dists = query_collection(client, args.collection, embedding, args.top_k)

    # Query CN collection if requested
    cn_docs, cn_metas, cn_dists = [], [], []
    if include_cn:
        cn_docs, cn_metas, cn_dists = query_collection(client, "scp_items_cn", embedding, args.top_k)

    # Merge and sort by distance (ascending)
    combined = []
    for doc, meta, dist in zip(en_docs, en_metas, en_dists):
        combined.append((dist, doc, meta, "EN"))
    for doc, meta, dist in zip(cn_docs, cn_metas, cn_dists):
        combined.append((dist, doc, meta, "CN"))

    combined.sort(key=lambda x: x[0])
    combined = combined[:args.top_k]

    if not combined:
        print("No results found. The vector database may be empty.")
        sys.exit(0)

    print(f"\nTop {len(combined)} results:\n")
    for i, (dist, doc, meta, branch) in enumerate(combined, 1):
        title = meta.get("title", "")
        scp_number = meta.get("scp_number", "")
        url = meta.get("url", "")
        author = meta.get("author", "")
        tags = meta.get("tags", "")

        header = f"SCP-{scp_number}" if scp_number else title or "Unknown"
        print(f"[{i}] [{branch}] {header}")
        print(f"    Title: {title}")
        print(f"    Author: {author}")
        print(f"    URL: {url}")
        print(f"    Tags: {tags}")
        print(f"    Distance: {dist:.4f}")
        preview = doc.replace("\n", " ")[:200]
        print(f"    Preview: {preview}...")
        print()


if __name__ == "__main__":
    main()
