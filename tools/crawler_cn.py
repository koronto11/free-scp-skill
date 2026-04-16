#!/usr/bin/env python3
"""
Optimized Wikidot crawler for the SCP Foundation Chinese Branch.
Fetches SCP translations (SCP-001..9999) and original SCP-CN entries.
Outputs a JSON file compatible with the English data pipeline.

Optimizations:
- Uses ?action=render for lightweight, core-content-only pages.
- Concurrent fetching via ThreadPoolExecutor (8 workers by default).
- Intelligent retries with exponential backoff; 404s are skipped immediately.
- Pre-filters empty/locked slots during series-page scanning.
- Automatic checkpointing every 100 pages for crash recovery.
- Respects HTTP_PROXY / HTTPS_PROXY from the environment.
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE_URL = "http://scp-wiki-cn.wikidot.com"

SERIES_PAGES = [
    "/scp-series",
    "/scp-series-2",
    "/scp-series-3",
    "/scp-series-4",
    "/scp-series-5",
    "/scp-series-6",
    "/scp-series-7",
    "/scp-series-8",
    "/scp-series-9",
    "/scp-series-10",
    "/scp-series-cn",
    "/scp-series-cn-2",
    "/scp-series-cn-3",
]

MAX_WORKERS = 8
PAGE_DELAY = (0.3, 0.8)
CHECKPOINT_INTERVAL = 100
TIMEOUT = 30

INVALID_TITLE_PATTERNS = [
    r"^ACCESS\s+DENIED",
    r"^\[锁定\]",
    r"^\[限制\]",
    r"^（无内容）",
    r"^\(无内容\)",
    r"^\[REDACTED\]",
    r"^ACCESS\s+RESTRICTED",
    r"^PAGE\s+NOT\s+FOUND",
]


def create_session(no_proxy: bool = False) -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )

    if no_proxy:
        session.trust_env = False
        session.proxies = {}
        print("Proxy disabled by --no-proxy.")
    else:
        proxies = {}
        for key in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
            val = os.environ.get(key)
            if val:
                scheme = "http" if "http" in key.lower() and "https" not in key.lower() else "https"
                proxies[scheme] = val
        if proxies:
            session.proxies.update(proxies)
            print(f"Using proxy: {proxies}")

    return session


def fetch_url(session: requests.Session, url: str, timeout: int = TIMEOUT, max_retries: int = 3) -> str:
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content.decode("utf-8", errors="replace")
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 404:
                raise
            last_err = exc
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_err = exc

        if attempt < max_retries:
            sleep_time = 2 * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(sleep_time)

    raise last_err


def is_valid_title(title: str) -> bool:
    if not title:
        return False
    for pattern in INVALID_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return False
    return True


def is_empty_slot(link: str, title: str) -> bool:
    if not title or len(title.strip()) <= 3:
        return True
    # Normalize to compare just the numeric part
    expected = link.upper().replace("SCP-", "").replace("CN-", "").strip()
    title_norm = title.upper().replace("SCP-", "").replace("CN-", "").strip()
    if title_norm == expected:
        return True
    return False


def parse_series_page(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    page_content = soup.find("div", {"id": "page-content"})
    if not page_content:
        return []

    entries = []
    seen = set()

    for li in page_content.find_all("li"):
        a = li.find("a", href=re.compile(r"^/scp(-cn)?-\d+[a-z]?$", re.IGNORECASE))
        if not a:
            continue

        href = a["href"].strip().lower()
        link = href.lstrip("/")
        if link in seen:
            continue
        seen.add(link)

        full_text = li.get_text(separator=" ", strip=True)
        title = ""
        for sep in (" - ", " — ", "–"):
            if sep in full_text:
                title = full_text.split(sep, 1)[-1].strip()
                break

        if not is_valid_title(title) or is_empty_slot(link, title):
            continue

        scp_number = link.replace("scp-", "").replace("cn-", "cn-")
        entries.append(
            {
                "link": link,
                "title": title,
                "scp_number": scp_number,
                "url": f"{BASE_URL}/{link}",
            }
        )

    return entries


def extract_tags(html: str) -> list:
    tags = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            m = re.match(r"/system:page-tags/tag/(.+)", a["href"])
            if m:
                raw_tag = m.group(1).split("#")[0]
                tag_name = urllib.parse.unquote(raw_tag).replace("-", " ")
                if tag_name and tag_name.lower() not in ("中心", "pages", "page"):
                    tags.append(tag_name)
    except Exception:
        pass

    seen = set()
    unique_tags = []
    for t in tags:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            unique_tags.append(t)
    return unique_tags


def clean_html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Focus only on the actual page content
    page_content = soup.find("div", {"id": "page-content"})
    if page_content:
        root = page_content
    else:
        root = soup

    # Remove noisy internal elements
    for selector in [
        "script",
        "style",
        "iframe",
        "img",
        "object",
        "embed",
        "audio",
        "video",
        "div.list-pages-box",
        "div.scp-image-block",
        "div.rate-box",
        "div.page-tags",
        "div.yui-navset",
        "footer",
        "nav",
        "header",
        "aside",
    ]:
        for tag in root.select(selector):
            tag.decompose()

    text = root.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Strip leading navigation crumbs that survive inside page-content
    nav_keywords = [
        "SCP基金会", "控制，收容，保护", "SCP系列", "系列 ", "搞笑SCP",
        "已解明SCP", "故事", "基金会故事", "设定", "故事系列", "事故报告",
        "Creepy-Pasta", "图书馆", "用户推荐清单", "异常物品记录",
        "超常现象记录", "未解明地点记录", "GoI格式", "音频记录",
        "艺术作品", "征文竞赛", "被放逐者之图书馆", "原创图书馆中心",
        "SCP-CN系列", "CN系列 ", "» ", "原创", "翻译",
    ]

    cleaned_lines = []
    for line in lines:
        # Skip lines that are purely navigation keywords
        if any(line.startswith(kw) for kw in nav_keywords):
            continue
        if line in ("控制，收容，保护", "SCP基金会"):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def parse_scp_page(html: str, meta: dict) -> dict:
    tags = extract_tags(html)
    raw_text = clean_html_to_text(html)
    return {
        **meta,
        "raw_content": raw_text,
        "tags": tags,
    }


def crawl_single_article(session: requests.Session, meta: dict) -> tuple:
    url = f"{meta['url']}?action=render"
    try:
        html = fetch_url(session, url, timeout=TIMEOUT, max_retries=3)
        article = parse_scp_page(html, meta)
        time.sleep(random.uniform(*PAGE_DELAY))
        return "success", article, None
    except requests.exceptions.HTTPError as exc:
        if exc.response.status_code == 404:
            return "skip", None, f"404: {meta['url']}"
        return "error", None, f"HTTP {exc.response.status_code}: {meta['url']}"
    except Exception as exc:
        return "error", None, f"{type(exc).__name__}: {exc}"


def _save_results(path: Path, data: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_checkpoint(path: Path, completed: set, failed: dict, results: list):
    ckpt = {
        "completed": sorted(completed),
        "failed": failed,
        "results": results,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ckpt, f, ensure_ascii=False, indent=2)


def crawl_cn(output_path: Path, limit: int = 0, workers: int = MAX_WORKERS, no_proxy: bool = False):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_path.with_suffix(".checkpoint.json")

    session = create_session(no_proxy=no_proxy)

    # 1. Scan series pages
    print("Scanning series pages for article links...")
    all_entries = []
    seen_links = set()
    for series_path in SERIES_PAGES:
        url = f"{BASE_URL}{series_path}"
        try:
            html = fetch_url(session, url, timeout=TIMEOUT, max_retries=3)
            entries = parse_series_page(html)
            new_entries = [e for e in entries if e["link"] not in seen_links]
            seen_links.update(e["link"] for e in new_entries)
            all_entries.extend(new_entries)
            print(f"  {series_path}: found {len(new_entries)} valid entries ({len(entries)} total)")
        except Exception as exc:
            print(f"  WARNING: failed to fetch {series_path}: {exc}", file=sys.stderr)

    print(f"\nTotal unique articles to crawl: {len(all_entries)}")
    if limit > 0:
        all_entries = all_entries[:limit]
        print(f"(Limited to first {limit} articles for testing)")

    # 2. Load checkpoint
    completed = set()
    failed = {}
    results = []
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            completed = set(ckpt.get("completed", []))
            failed = ckpt.get("failed", {})
            results = ckpt.get("results", [])
            print(f"Resumed from checkpoint: {len(completed)} done, {len(failed)} failed")
        except Exception as exc:
            print(f"WARNING: failed to load checkpoint: {exc}", file=sys.stderr)

    pending = [e for e in all_entries if e["link"] not in completed and e["link"] not in failed]
    print(f"Pending articles: {len(pending)}")

    if not pending:
        print("All articles already processed.")
        _save_results(output_path, results)
        return

    # 3. Concurrent crawl
    new_completed = []
    new_failed = {}
    new_results = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_link = {
            executor.submit(crawl_single_article, session, entry): entry["link"]
            for entry in pending
        }

        pbar = tqdm(total=len(pending), desc="Crawling CN articles")
        for future in as_completed(future_to_link):
            link = future_to_link[future]
            try:
                status, article, error = future.result()
                if status == "success":
                    new_results.append(article)
                    new_completed.append(link)
                elif status == "skip":
                    new_failed[link] = error
                else:
                    new_failed[link] = error
            except Exception as exc:
                new_failed[link] = f"Future error: {exc}"

            pbar.update(1)

            processed = len(new_completed) + len(new_failed)
            if processed % CHECKPOINT_INTERVAL == 0:
                _save_checkpoint(
                    checkpoint_path,
                    completed | set(new_completed),
                    {**failed, **new_failed},
                    results + new_results,
                )
        pbar.close()

    # 4. Final save
    final_results = results + new_results
    final_completed = completed | set(new_completed)
    final_failed = {**failed, **new_failed}
    _save_results(output_path, final_results)
    _save_checkpoint(checkpoint_path, final_completed, final_failed, final_results)

    print(f"\nSaved {len(final_results)} articles to {output_path}")
    print(f"Total completed: {len(final_completed)} | Failed: {len(final_failed)}")


def main():
    parser = argparse.ArgumentParser(description="Crawl SCP Foundation Chinese Branch.")
    parser.add_argument("--output", type=str, default="cn_articles.json", help="Output JSON file path.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of articles to crawl (0 = unlimited).")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Number of concurrent threads.")
    parser.add_argument("--no-proxy", action="store_true", help="Ignore system proxy settings.")
    args = parser.parse_args()

    crawl_cn(Path(args.output), limit=args.limit, workers=args.workers, no_proxy=args.no_proxy)


if __name__ == "__main__":
    main()
