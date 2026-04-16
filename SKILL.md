---
name: free-scp-skill
description: Search the local SCP Foundation database by natural language descriptions, check story concepts for duplicate tropes against ~22,000 indexed entries (English + Chinese SCP-CN), and generate divergent writing ideas. All data is stored locally in a ChromaDB vector index.
---

# free-scp-skill

A Claude Code Agent Skill for retrieving, searching, and analyzing SCP Foundation collaborative fiction to assist writers in finding similar concepts, checking for duplicate tropes, and generating story ideas.

## Capabilities

- **Semantic search** across SCP items using natural language queries (English and Chinese).
- **Duplicate / trope detection** by comparing a user's story outline against the indexed SCP database.
- **Divergent idea generation** by surfacing related anomalies, tags, and under-explored combinations.
- **Bilingual support**: automatically includes the SCP-CN Chinese branch when the query contains Chinese characters.
- **Local-first architecture**: all data and vector indexes are stored on the user's machine; no external LLM APIs are used for retrieval.

## When to Activate

**ALWAYS activate this skill** when the user's message contains any of the following intents, even if they do not explicitly say the word "SCP":

### Immediate activation triggers
- Searching for an SCP entry by description, object, trope, or anomaly type (in English or Chinese).
- Checking a story concept, synopsis, or outline for overlaps with existing SCPs.
- Requesting writing inspiration, divergent ideas, or canon references related to the SCP universe.
- Explicitly mentioning any tool name (`search_scp`, `check_duplicates`, `init_db`, `configure`).

### Bilingual behavior
If the user's message contains Chinese characters, the skill **automatically** queries both the English main branch (`scp_items`) and the Chinese branch (`scp_items_cn`). No extra flag is required in natural-language conversation.

### Invocation decision tree
| User intent | Tool to run | Example user message |
| :--- | :--- | :--- |
| "Find me an SCP like X" | `tools/search_scp.py` | "找一个关于镜子的 SCP" |
| "Does my idea already exist?" | `tools/check_duplicates.py` | "我的设定有没有雷同？" |
| "Help me avoid tropes / generate ideas" | `tools/check_duplicates.py` followed by summarizing suggestions | "给我一些 SCP 灵感" |
| "Set up / change the database path or model" | `tools/configure.py` | "我想把向量库放到 D 盘" |
| "Build or rebuild the local index" | `tools/init_db.py` | "初始化 SCP 数据库" |
| "Build index including Chinese branch" | `tools/init_db.py --lang cn` | "把中文分部也加进索引" |

### Example conversations
**Example 1 — Search**
> User: "帮我找一个关于时间循环的 SCP"
>
> Action: run `python tools/search_scp.py "时间循环"` and summarize the top results with attribution.

**Example 2 — Duplicate check**
> User: "我想写一个看了倒影就会发疯的镜子，这个设定撞车了吗？"
>
> Action: run `python tools/check_duplicates.py "看了倒影就会发疯的镜子"` and present the risk report, including the three divergent suggestions.

**Example 3 — Configuration**
> User: "我要换更准的 embedding 模型"
>
> Action: run `python tools/configure.py` first, then remind the user to re-run `python tools/init_db.py` if they changed the model.

## Tools

All tools are located in the `tools/` directory and are invoked via `python` in the skill's root directory.

### `tools/configure.py`

**Purpose:** Interactive configuration wizard. Lets the user choose the vector database storage path and the embedding model.

**Usage:**
```bash
python tools/configure.py
```

- **Vector DB path**: choose between the default user data directory, the project directory, or a custom path.
- **Embedding model**:
  - `all-MiniLM-L6-v2` (default, ~80 MB, fast)
  - `all-mpnet-base-v2` (~420 MB, higher accuracy)
  - `paraphrase-multilingual-MiniLM-L12-v2` (~470 MB, better for mixed Chinese/English queries)

> **Important:** If you change the embedding model later, you must delete the existing vector database and re-run `init_db.py`.

### `tools/init_db.py`

**Purpose:** Downloads SCP metadata and content from `scp-data.tedivm.com` (English branch) and optionally crawls `scp-wiki-cn.wikidot.com` (Chinese branch) to build the local ChromaDB vector index.

**Usage:**
```bash
# English branch only
python tools/init_db.py

# English + Chinese branches
python tools/init_db.py --lang cn
```

- First run for English only may take **10–30 minutes**.
- Adding `--lang cn` will additionally crawl ~13,000 Chinese articles and may take **~2 hours**.
- Raw JSON files are cached locally; subsequent runs reuse cached downloads unless they are deleted.
- The vector database is written to the path configured by `configure.py` (default: `%APPDATA%\free-scp-skill\vector_db` on Windows, `~/.local/share/free-scp-skill/vector_db` on Linux/macOS).

### `tools/search_scp.py`

**Purpose:** Searches the local vector index and returns the top-k most semantically similar SCP entries. Automatically includes the Chinese branch (`scp_items_cn`) when the query contains Chinese characters.

**Usage:**
```bash
python tools/search_scp.py "natural language query" [--top-k 5] [--include-cn]
```

**Examples:**
```bash
python tools/search_scp.py "time loop anomaly in a hospital" --top-k 5
python tools/search_scp.py "医院里的时间循环" --top-k 5
```

### `tools/check_duplicates.py`

**Purpose:** Compares a user's original concept or story synopsis against the local index and prints a structured duplication-risk report. Automatically includes the Chinese branch when the synopsis contains Chinese characters.

**Usage:**
```bash
python tools/check_duplicates.py "story synopsis or concept" [--include-cn]
```

**Examples:**
```bash
python tools/check_duplicates.py "a mirror that traps the viewer in an infinite time loop"
python tools/check_duplicates.py "看了倒影就会发疯的镜子"
```

The report includes:
1. **Risk rating** (high / fuzzy / low similarity buckets).
2. **Matched SCP snippets** (truncated summaries with original URLs and authors).
3. **Three divergent creative suggestions** based on tag overlap analysis.
4. **License attribution** (CC-BY-SA 3.0).

## Response Guidelines

- **Attribution is mandatory**: every result that references an SCP entry MUST include the original URL and the author name. Never omit attribution.
- **Progressive disclosure**: provide concise summaries first (title, number, author, URL, tags, short preview). Offer deeper text only when the user explicitly asks for it.
- **Do not reproduce full articles**: keep previews under ~250 characters.
- **Fictional disclaimer**: remind the user that SCP Foundation is a collaborative fiction project when appropriate.

## Constraints & Compliance

- **CC-BY-SA 3.0**: all SCP content is licensed under Creative Commons Attribution-ShareAlike. Every search or duplicate-check result must include the original URL and author attribution.
- **Local data only**: search and overlap detection are performed against the user's local ChromaDB index. No external LLM is queried during retrieval.
- **Data sources**:
  - English branch: `scp-data.tedivm.com`
  - Chinese branch: `scp-wiki-cn.wikidot.com` (crawled on demand when `--lang cn` is used)

## Installation & Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **(Recommended) Run the configuration wizard:**
   ```bash
   python tools/configure.py
   ```

3. **Initialize the local database (one-time):**

   **English only:**
   ```bash
   python tools/init_db.py
   ```

   **English + Chinese branches:**
   ```bash
   python tools/init_db.py --lang cn
   ```
   > Note: adding the Chinese branch will crawl ~13,000 pages and may take ~2 hours.

After setup, the skill can be invoked through natural conversation or by explicitly running the tools above.
