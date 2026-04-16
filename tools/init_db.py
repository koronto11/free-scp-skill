#!/usr/bin/env python3
"""
Initialize the local SCP vector database.
Downloads metadata and content from scp-data.tedivm.com,
generates embeddings, and stores them in ChromaDB.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config_utils import get_data_dir, get_config

# Data source URLs
BASE_URL = "https://scp-data.tedivm.com"
ITEMS_INDEX_URL = f"{BASE_URL}/data/scp/items/index.json"
ITEMS_CONTENT_INDEX_URL = f"{BASE_URL}/data/scp/items/content_index.json"
TALES_INDEX_URL = f"{BASE_URL}/data/scp/tales/index.json"
TALES_CONTENT_INDEX_URL = f"{BASE_URL}/data/scp/tales/content_index.json"


def download_json(url, timeout=60):
    """Download and parse a JSON file from a URL."""
    print(f"Downloading {url} ...")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def save_json(data, path):
    """Save data to a local JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path):
    """Load JSON from a local file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_chroma():
    """Lazy import chromadb to fail gracefully if not installed."""
    try:
        import chromadb
        return chromadb
    except ImportError as exc:
        print("ERROR: chromadb is not installed. Run: pip install chromadb")
        raise SystemExit(1) from exc


def ensure_sentence_transformers(model_name: str):
    """Lazy import sentence_transformers and load the chosen model."""
    try:
        from sentence_transformers import SentenceTransformer
        print(f"Loading embedding model ({model_name})...")
        return SentenceTransformer(model_name)
    except ImportError as exc:
        print("ERROR: sentence-transformers is not installed. Run: pip install sentence-transformers")
        raise SystemExit(1) from exc


def clean_html(text: str) -> str:
    """Strip HTML tags and common entities from raw wiki content."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_text_for_embedding(entry, full_text=False):
    """
    Build a single searchable text block from an SCP entry.
    We include title, tags, and a truncated (or full) version of the raw content.
    """
    parts = []
    title = entry.get("title", "")
    scp_number = entry.get("scp_number", "")
    tags = entry.get("tags", [])
    raw_content = entry.get("raw_content", "")

    if scp_number:
        parts.append(f"SCP-{scp_number}")
    if title:
        parts.append(f"Title: {title}")
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    if raw_content:
        text = clean_html(raw_content)
        if not full_text:
            text = text[:2000]
        parts.append(f"Content: {text}")

    return "\n".join(parts)


def fetch_and_index_items(data_dir, chroma_client, model, collection_name="scp_items", full_text=False):
    """Download SCP items metadata and content, then index into ChromaDB."""
    raw_dir = data_dir / "data"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download index
    index_path = raw_dir / "items_index.json"
    if not index_path.exists():
        index = download_json(ITEMS_INDEX_URL)
        save_json(index, index_path)
    else:
        print(f"Using cached {index_path}")
        index = load_json(index_path)

    # 2. Download content index
    content_index_path = raw_dir / "items_content_index.json"
    if not content_index_path.exists():
        content_index = download_json(ITEMS_CONTENT_INDEX_URL)
        save_json(content_index, content_index_path)
    else:
        print(f"Using cached {content_index_path}")
        content_index = load_json(content_index_path)

    # 3. Build a lookup from link -> metadata
    if isinstance(index, dict):
        index_entries = index.values()
    else:
        index_entries = index
    meta_lookup = {entry["link"]: entry for entry in index_entries if "link" in entry}

    # 4. Download each series content file and merge with metadata
    collection = chroma_client.get_or_create_collection(name=collection_name)

    # Gather all entries first so we can batch-embed
    documents = []
    metadatas = []
    ids = []

    series_map = content_index.get("series", content_index)
    if isinstance(series_map, dict):
        series_iter = series_map.items()
    else:
        series_iter = enumerate(series_map)

    for series_key, content_relative_path in tqdm(list(series_iter), desc="Loading content files"):
        content_url = f"{BASE_URL}/data/scp/items/{content_relative_path}"
        content_file_name = Path(content_relative_path).name
        local_content_path = raw_dir / "items_content" / content_file_name

        if not local_content_path.exists():
            local_content_path.parent.mkdir(parents=True, exist_ok=True)
            content_data = download_json(content_url)
            save_json(content_data, local_content_path)
        else:
            with open(local_content_path, "r", encoding="utf-8") as f:
                content_data = json.load(f)

        if isinstance(content_data, list):
            entries = content_data
        elif isinstance(content_data, dict):
            if "entries" in content_data:
                entries = content_data["entries"]
            else:
                entries = list(content_data.values())
        else:
            entries = []
        for entry in entries:
            link = entry.get("link")
            if not link:
                continue
            meta = meta_lookup.get(link, {})
            merged = {**meta, **entry}

            doc_text = build_text_for_embedding(merged, full_text=full_text)
            if not doc_text.strip():
                continue

            doc_id = f"item_{link}"
            # Avoid duplicates if re-running
            if doc_id in ids:
                continue

            documents.append(doc_text)
            metadatas.append({
                "link": link,
                "title": merged.get("title", ""),
                "scp_number": str(merged.get("scp_number", "")),
                "url": merged.get("url", ""),
                "tags": ", ".join(merged.get("tags", [])),
                "author": merged.get("creator", ""),
                "source": "scp_items",
            })
            ids.append(doc_id)

    if not documents:
        print("No documents found to index.")
        return

    # 5. Batch embed and insert
    print(f"Embedding {len(documents)} documents...")
    batch_size = 128
    for i in tqdm(range(0, len(documents), batch_size), desc="Indexing"):
        batch_docs = documents[i:i + batch_size]
        batch_meta = metadatas[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        embeddings = model.encode(batch_docs, show_progress_bar=False).tolist()
        collection.add(
            embeddings=embeddings,
            documents=batch_docs,
            metadatas=batch_meta,
            ids=batch_ids,
        )

    print(f"Indexed {len(documents)} SCP items into collection '{collection_name}'.")


def main():
    parser = argparse.ArgumentParser(description="Initialize the local SCP vector database.")
    parser.add_argument("--lang", type=str, default="", help="Additional language branch (e.g., 'cn').")
    args = parser.parse_args()

    cfg = get_config()
    data_dir = get_data_dir()
    vector_db_path = cfg["vector_db_path"]
    embedding_model = cfg["embedding_model"]

    print(f"Data directory: {data_dir}")
    print(f"Vector DB path: {vector_db_path}")
    print(f"Embedding model: {embedding_model}")

    chromadb = ensure_chroma()
    client = chromadb.PersistentClient(path=vector_db_path)

    model = ensure_sentence_transformers(embedding_model)

    fetch_and_index_items(data_dir, client, model)

    if args.lang == "cn":
        fetch_and_index_cn(data_dir, client, model)

    print("Initialization complete.")


def fetch_and_index_cn(data_dir, client, model, collection_name="scp_items_cn", full_text=False):
    """Crawl SCP-CN branch and index into ChromaDB."""
    raw_dir = data_dir / "data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cn_json_path = raw_dir / "cn_articles.json"

    if not cn_json_path.exists():
        print("Crawling SCP-CN branch... this may take ~2 hours for ~13,000 articles.")
        # Import here to avoid top-level dependency issues
        crawler_cn_path = Path(__file__).parent / "crawler_cn.py"
        if not crawler_cn_path.exists():
            print("ERROR: crawler_cn.py not found. Cannot index Chinese branch.")
            raise SystemExit(1)
        # Run crawler_cn as a subprocess so we don't need to import its globals
        import subprocess
        subprocess.run(
            [sys.executable, str(crawler_cn_path), "--output", str(cn_json_path)],
            check=True,
        )
    else:
        print(f"Using cached {cn_json_path}")

    with open(cn_json_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    collection = client.get_or_create_collection(name=collection_name)

    documents = []
    metadatas = []
    ids = []

    for entry in articles:
        link = entry.get("link")
        if not link:
            continue

        doc_text = build_text_for_embedding(entry, full_text=full_text)
        if not doc_text.strip():
            continue

        doc_id = f"cn_{link}"
        if doc_id in ids:
            continue

        documents.append(doc_text)
        metadatas.append({
            "link": link,
            "title": entry.get("title", ""),
            "scp_number": str(entry.get("scp_number", "")),
            "url": entry.get("url", ""),
            "tags": ", ".join(entry.get("tags", [])),
            "author": "",  # crawler_cn currently does not extract author
            "source": "scp_items_cn",
        })
        ids.append(doc_id)

    if not documents:
        print("No CN documents found to index.")
        return

    print(f"Embedding {len(documents)} CN documents...")
    batch_size = 128
    for i in tqdm(range(0, len(documents), batch_size), desc="Indexing CN"):
        batch_docs = documents[i:i + batch_size]
        batch_meta = metadatas[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        embeddings = model.encode(batch_docs, show_progress_bar=False).tolist()
        collection.add(
            embeddings=embeddings,
            documents=batch_docs,
            metadatas=batch_meta,
            ids=batch_ids,
        )

    print(f"Indexed {len(documents)} CN SCP items into collection '{collection_name}'.")


def main():
    parser = argparse.ArgumentParser(description="Initialize the local SCP vector database.")
    parser.add_argument("--lang", type=str, default="", help="Additional language branch (e.g., 'cn').")
    parser.add_argument("--all", action="store_true", help="Index the full article text instead of truncating to ~2000 chars.")
    args = parser.parse_args()

    cfg = get_config()
    data_dir = get_data_dir()
    vector_db_path = cfg["vector_db_path"]
    embedding_model = cfg["embedding_model"]

    print(f"Data directory: {data_dir}")
    print(f"Vector DB path: {vector_db_path}")
    print(f"Embedding model: {embedding_model}")
    if args.all:
        print("Mode: FULL TEXT indexing (no truncation). This will use significantly more disk space and memory.")

    chromadb = ensure_chroma()
    client = chromadb.PersistentClient(path=vector_db_path)

    model = ensure_sentence_transformers(embedding_model)

    fetch_and_index_items(data_dir, client, model, full_text=args.all)

    if args.lang == "cn":
        fetch_and_index_cn(data_dir, client, model, full_text=args.all)

    print("Initialization complete.")


if __name__ == "__main__":
    main()
