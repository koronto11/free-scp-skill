#!/usr/bin/env python3
"""
Compare a user story synopsis against the local SCP index to detect potential overlaps.
Returns a structured duplication-risk report with divergence suggestions.
"""

import argparse
import os
import random
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


def cosine_to_similarity(dist: float) -> float:
    """
    Convert ChromaDB cosine distance (range 0..2) to a 0-100 % similarity score.
    similarity = 1 - (dist / 2)
    """
    sim = 1.0 - (dist / 2.0)
    sim = max(0.0, min(1.0, sim))
    return sim * 100.0


def clean_htmlish(text: str) -> str:
    """Strip obvious HTML clutter for the snippet."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&quot;", '"').replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_snippet(doc_text: str, max_len: int = 220) -> str:
    """Pull out the 'Content:' portion and truncate it."""
    if "Content:" in doc_text:
        snippet = doc_text.split("Content:", 1)[-1].strip()
    else:
        snippet = doc_text.strip()
    snippet = clean_htmlish(snippet)
    return snippet[:max_len] + ("..." if len(snippet) > max_len else "")


def extract_risk_tags(metas):
    """Collect common tags from high-risk matches for contrast logic."""
    tags = set()
    for m in metas:
        t = m.get("tags") or ""
        if isinstance(t, str):
            tags.update({x.strip() for x in t.split(",") if x.strip()})
        elif isinstance(t, list):
            tags.update(t)
    return tags


SUGGESTION_SEEDS = [
    {
        "title": "社会传播链",
        "template": (
            "让'{trigger}'本身成为二次传播媒介。受害者如果向他人详细描述该异常，"
            "听者会在特定延迟后同样触发。这从'单一物件异常'升级为'信息危害'，"
            "显著扩展收容难度。"
        ),
        "keywords": {"infohazard", "cognitohazard", "memetic"},
    },
    {
        "title": "可逆但非人道的出口",
        "template": (
            "异常可以被终止，但条件是：必须有另一个人自愿接管受害者的状态。"
            "基金会利用 D 级人员进行定期'轮换'收容，引发伦理争议与内部叙事张力。"
        ),
        "keywords": {"humanoid", "ethical", "foundation"},
    },
    {
        "title": "感官悖论",
        "template": (
            "某种生理缺陷（如失明、失聪）本应使人免疫，但后续发现该群体却能"
            "以另一种未知感官'感知'到异常。这暗示异常不依赖常规感官，"
            "而是更底层的认知入侵。"
        ),
        "keywords": {"cognitohazard", "sensory", "perception"},
    },
    {
        "title": "反熵元素",
        "template": (
            "将'{object}'与局部熵减结合：异常区域内的物理过程会自发逆序进行。"
            "破碎的玻璃自动愈合、泼出的水回到杯中，但代价是受害者自身加速衰老。"
        ),
        "keywords": {"thermal", "temporal", "physical"},
    },
    {
        "title": "儿童视角",
        "template": (
            "将异常对象设定为常见的儿童玩具/校园物品。基金会需要在学校、"
            "家庭等日常场景中进行隐蔽收容。成人与儿童对该异常的反应差异"
            "成为核心叙事驱动力。"
        ),
        "keywords": {"child", "toy", "school"},
    },
    {
        "title": "空间异常嵌套",
        "template": (
            "'{object}'内部或影响范围内存在一个拓扑上不可能的空间结构。"
            "受害者进入后会发现空间尺度远大于外部观测值，且出口位置"
            "会随时间或观察状态改变。"
        ),
        "keywords": {"spatial", "dimensional", "structure"},
    },
]


def generate_suggestions(query: str, risk_tags: set) -> list:
    """Pick 3 suggestion seeds that least overlap with the matched SCP tags."""
    scored = []
    for seed in SUGGESTION_SEEDS:
        overlap = len(seed["keywords"] & risk_tags)
        scored.append((overlap, random.random(), seed))
    scored.sort()
    picked = [s[2] for s in scored[:3]]

    object_guess = query.strip().split()[0] if query.strip() else "该异常"
    trigger_guess = query.strip().split()[-1] if query.strip() else "接触"

    results = []
    labels = ["A", "B", "C"]
    for label, seed in zip(labels, picked):
        text = seed["template"].format(object=object_guess, trigger=trigger_guess)
        overlap_note = (
            "（当前匹配结果中未见此组合方向）"
            if not (seed["keywords"] & risk_tags)
            else "（与现有匹配项的标签重叠度较低）"
        )
        results.append((label, seed["title"], text, overlap_note))
    return results


def print_report(query: str, docs, metas, dists, total_count: int, branches: dict):
    sims = [cosine_to_similarity(d) for d in dists]

    high = [(i, sims[i]) for i in range(len(sims)) if sims[i] >= 80]
    fuzzy = [(i, sims[i]) for i in range(len(sims)) if 50 <= sims[i] < 80]
    low = [(i, sims[i]) for i in range(len(sims)) if sims[i] < 50]

    risk_tags = extract_risk_tags([metas[i] for i, _ in (high + fuzzy)])

    scope_parts = ["英文主站"]
    if branches.get("cn", 0) > 0:
        scope_parts.append("中文分部")
    scope_label = " + ".join(scope_parts)

    print("=" * 55)
    print("SCP 原创设定查重报告")
    print("=" * 55)
    print()
    print(f"查询内容：{query}")
    print(f"检索范围：{scope_label} SCP Items（约 {total_count:,} 条目）")
    print("匹配阈值：相似度 ≥ 50%")
    print()
    print("-" * 55)
    print("【风险评级】")
    print("-" * 55)

    if high:
        level = "⚠️  高风险"
    elif fuzzy:
        level = "⚡ 中风险"
    else:
        level = "✅ 低风险 / 相对新颖"

    print(f"{level}")
    print(f"  - 高危匹配：{len(high)} 篇（相似度 ≥ 80%）")
    print(f"  - 模糊匹配：{len(fuzzy)} 篇（相似度 50%-80%）")
    print(f"  - 低危/新颖：{len(low)} 篇（相似度 < 50%）")
    print("  注：风险评级仅供参考，是否撞车请结合原文片段自行判断。")
    print()

    def print_group(name, indices):
        if not indices:
            print(f"【{name}】")
            print("  无")
            print()
            return
        print(f"【{name}】")
        for rank, (idx, sim) in enumerate(indices, 1):
            meta = metas[idx]
            doc = docs[idx]
            title = meta.get("title") or "Unknown"
            scp_number = meta.get("scp_number") or ""
            url = meta.get("url") or ""
            author = meta.get("author") or meta.get("creator") or "Unknown"
            tags = meta.get("tags") or ""
            branch = meta.get("branch", "EN")
            header = f"SCP-{scp_number}" if scp_number else title

            snippet = extract_snippet(doc)
            print(f"  [{rank}] [{branch}] {header}（相似度 {sim:.1f}%）")
            print(f"       标题：{title}")
            print(f"       作者：{author}")
            print(f"       链接：{url}")
            print(f"       标签：{tags}")
            print(f"       片段：{snippet}")
            print()

    print_group("高危匹配", high)
    print_group("模糊匹配", fuzzy)

    if low:
        print("【低危 / 参考匹配】")
        for rank, (idx, sim) in enumerate(low[:3], 1):
            meta = metas[idx]
            scp_number = meta.get("scp_number") or ""
            title = meta.get("title") or "Unknown"
            branch = meta.get("branch", "EN")
            header = f"SCP-{scp_number}" if scp_number else title
            print(f"  [{rank}] [{branch}] {header}（相似度 {sim:.1f}%）")
        print()

    print("-" * 55)
    print("【创作建议 · 发散思维】")
    print("-" * 55)
    suggestions = generate_suggestions(query, risk_tags)
    for label, title, text, note in suggestions:
        print()
        print(f"{label}. {title}")
        print(f"   {text}")
        print(f"   {note}")
    print()

    print("-" * 55)
    print("【数据来源与合规声明】")
    print("-" * 55)
    if branches.get("cn", 0) > 0:
        print("数据来源：scp-data.tedivm.com（英文主站）+ scp-wiki-cn.wikidot.com（中文分部）")
    else:
        print("数据来源：scp-data.tedivm.com（英文主站 SCP Foundation）")
    print("许可协议：CC-BY-SA 3.0")
    print("使用提示：本报告仅供创作参考，请避免直接复制原文设定。")
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(description="Check story synopsis for potential SCP duplicates/overlaps.")
    parser.add_argument("query", type=str, help="Your original SCP concept / synopsis.")
    parser.add_argument("--top-k", type=int, default=15, help="Max number of candidates to retrieve.")
    parser.add_argument("--collection", type=str, default="scp_items", help="ChromaDB collection name.")
    parser.add_argument("--include-cn", action="store_true", help="Also check against the Chinese branch collection.")
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

    print(f"Analyzing concept: '{args.query}' ...")
    print(f"Using embedding model: {embedding_model}")
    if auto_include_cn:
        print("Detected Chinese characters: automatically including SCP-CN branch.")

    model = SentenceTransformer(embedding_model)
    embedding = model.encode(args.query).tolist()

    # Query EN
    en_docs, en_metas, en_dists = query_collection(client, args.collection, embedding, args.top_k)
    en_count = len(en_docs)
    try:
        en_count = client.get_collection(name=args.collection).count()
    except Exception:
        pass

    # Query CN if needed
    cn_docs, cn_metas, cn_dists = [], [], []
    cn_count = 0
    if include_cn:
        cn_docs, cn_metas, cn_dists = query_collection(client, "scp_items_cn", embedding, args.top_k)
        try:
            cn_count = client.get_collection(name="scp_items_cn").count()
        except Exception:
            pass

    # Merge and sort
    combined = []
    for doc, meta, dist in zip(en_docs, en_metas, en_dists):
        combined.append((dist, doc, {**meta, "branch": "EN"}))
    for doc, meta, dist in zip(cn_docs, cn_metas, cn_dists):
        combined.append((dist, doc, {**meta, "branch": "CN"}))

    combined.sort(key=lambda x: x[0])
    combined = combined[:args.top_k]

    if not combined:
        print("No results found. The vector database may be empty.")
        sys.exit(0)

    docs = [c[1] for c in combined]
    metas = [c[2] for c in combined]
    dists = [c[0] for c in combined]
    branches = {"en": en_count, "cn": cn_count}
    total_count = en_count + cn_count

    print_report(args.query, docs, metas, dists, total_count, branches)


if __name__ == "__main__":
    main()
