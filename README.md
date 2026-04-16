# free-scp-skill

<div align="center">
  <img src="./assets/scp.gif" alt="SCP" />
</div>

<p align="center">
  <b>A local-first Claude Code Agent Skill for SCP Foundation semantic search, duplicate detection, and creative assistance.</b><br/>
  <b>一个纯本地运行的 Claude Code Agent Skill，用于 SCP 基金会的语义搜索、查重比对与创作辅助。</b>
</p>

---

## 项目初衷 | Project Vision

SCP 基金会是一个基于维基社区的协同写作小说项目，目前已积累超过 10,000 篇条目（含翻译与原创）。对于创作者而言，最大的痛点往往不是"没点子"，而是：**"这个点子有没有人写过？"**、**"我的设定和某篇 SCP 撞车了吗？"**、**"如何在已有框架下做出差异化？"**

`free-scp-skill` 的初衷就是解决这些问题。它将 SCP 条目转化为本地可检索的向量知识库，通过自然语言即可快速定位相关文档、检测设定雷同，并基于已有数据发散出差异化的创作方向。所有数据均存储在本地，无需依赖外部 LLM API，尊重开源社区的 CC-BY-SA 协议。

> The SCP Foundation is a collaborative fiction wiki with over 10,000 entries. For writers, the hardest part is rarely "no ideas" — it's "has this been done before?". This skill turns the entire SCP corpus into a locally-searchable vector knowledge base, letting you find related articles, check for trope overlaps, and generate divergent ideas using natural language. All data stays local; no external LLM APIs are required for retrieval.

---

## 技术选型 | Tech Stack

| 层级 | 技术 | 说明 |
| :--- | :--- | :--- |
| **向量数据库** | [ChromaDB](https://www.trychroma.com/) | 纯本地、零配置的嵌入式向量数据库，单文件 `chroma.sqlite3` 存储，无需守护进程。 |
| **文本向量化** | [sentence-transformers](https://www.sbert.net/) | 使用 `all-MiniLM-L6-v2`（默认，80MB，快速）或 `all-mpnet-base-v2`（更精准，420MB）将 SCP 文本转化为语义向量。 |
| **爬虫与数据清洗** | `requests`, `BeautifulSoup4` | 针对 Wikidot-CN 做了 `?action=render` 精简页面优化，过滤导航栏与 HTML 标签，提取核心纯文本。 |
| **数据缓存** | Local JSON + Checkpoint | 下载的原始元数据以 JSON 缓存到本地，支持断点续爬与增量更新。 |
| **运行环境** | Python 3.9+ | 完全本地运行，无云服务依赖，隐私性与可迁移性极佳。 |

---

## 快速开始 | Quick Start

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> Windows 用户若安装 `chromadb` 或 `sentence-transformers` 时遇到编译错误，请先安装 [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，然后重试。

### 2. 配置向导（可选但推荐）

```bash
python tools/configure.py
```

向导将引导你选择：
- **向量库存储路径**：可自定义到 D 盘或外接硬盘，避免 C 盘空间焦虑
- **Embedding 模型**：
  - `all-MiniLM-L6-v2` — 默认，快速，适合大多数场景
  - `all-mpnet-base-v2` — 更高精准度，适合对检索质量有极致要求的用户
  - `paraphrase-multilingual-MiniLM-L12-v2` — 中英文混合查询优化

### 3. 初始化本地数据库

```bash
# 仅索引英文主站（约 9,500 篇）
python tools/init_db.py

# 索引英文主站 + 中文分部（约 22,000 篇，推荐）
python tools/init_db.py --lang cn

# 全量存储正文（不截断 2000 字符）
python tools/init_db.py --lang cn --all
```

首次初始化耗时约 **10–40 分钟**（取决于网络、硬件与是否启用代理），后续会自动复用本地缓存。

---

## 功能展示 | Feature Showcase

### 语义搜索 | Semantic Search

```bash
python tools/search_scp.py "医院里的时间循环异常" --top-k 5
```

**输出示例：**

```
Encoding query: '医院里的时间循环异常' ...
Using embedding model: all-MiniLM-L6-v2
Detected Chinese characters: automatically including SCP-CN branch.

Top 5 results:

[1] [CN] SCP-5764
    Title: 这里什么都没有。
    Author: 
    URL: http://scp-wiki-cn.wikidot.com/scp-5764
    Tags: meta, safe, scp, 循环, 文件, 智能
    Distance: 1.1129
    Preview: SCP-5764 Title: 这里什么都没有。 Tags: meta, safe, scp, 循环, 文件, 智能 Content: « SCP-5763 | SCP-5764 | SCP-5765 »...

[2] [CN] SCP-5400
    Title: 系统错误
    Author: 
    URL: http://scp-wiki-cn.wikidot.com/scp-5400
    Tags: 5000, keter, scp, uiu, 人工智能, 全球超自然联盟, 合著, 未收容, 电子, 电脑, 管理员, 需更新
    Distance: 1.1491
    Preview: SCP-5400 Title: 系统错误 Tags: 5000, keter, scp, uiu, 人工智能, 全球超自然联盟, 合著, 未收容, 电子, 电脑, 管理员, 需更新 Content: « SCP-5399 | SCP-5400 | SCP-5401 »...
```

> 当查询中包含中文字符时，系统会自动同时检索英文主站（`scp_items`）与中文分部（`scp_items_cn`）两个集合，合并后返回最相关结果。

### 设定查重与创作辅助 | Duplicate Check & Divergence

```bash
python tools/check_duplicates.py "看了倒影就会发疯的镜子"
```

**输出示例：**

```
=======================================================
SCP 原创设定查重报告
=======================================================

查询内容：看了倒影就会发疯的镜子
检索范围：英文主站 + 中文分部 SCP Items（约 22,000 条目）
匹配阈值：相似度 ≥ 50%

-------------------------------------------------------
【风险评级】
-------------------------------------------------------
⚡ 中风险
  - 高危匹配：0 篇（相似度 ≥ 80%）
  - 模糊匹配：1 篇（相似度 50%-80%）
  - 低危/新颖：14 篇（相似度 < 50%）

【模糊匹配】
  [1] SCP-650（相似度 50.3%）
       标题：SCP-650
       作者：Dr Talson
       链接：https://scp-wiki.wikidot.com/scp-650
       标签：euclid, humanoid, observational, scp, sculpture, teleportation
       片段：Item #: SCP-650 Object Class: Euclid Special Containment Procedures: SCP-650 is to be stored in a lockable room at least 4 meters by 4 meters...

-------------------------------------------------------
【创作建议 · 发散思维】
-------------------------------------------------------
A. 社会传播链
   让异常本身成为二次传播媒介。受害者向他人描述倒影后，听者会在延迟后同样触发。
   （当前匹配结果中未见此组合方向）

B. 空间异常嵌套
   镜子内部或影响范围存在拓扑上不可能的空间结构，出口位置随观察状态改变。
   （当前匹配结果中未见此组合方向）

C. 感官悖论
   某种生理缺陷（如失明）本应免疫，但该群体却能以未知感官“感知”到异常。
   （当前匹配结果中未见此组合方向）
```

---

## 在 Claude Code 中集成 | Claude Code Integration

### 安装 Skill

在你的任意项目目录中运行：

```bash
claude skills add /path/to/free-scp-skill
```

或直接使用 GitHub 地址：

```bash
claude skills add https://github.com/koronto11/free-scp-skill
```

### 使用效果演示

安装后，在 Claude Code 对话中直接提问即可触发：

**用户：**
> Can you help me find an SCP related to Yellowstone National Park?

**Claude 自动调用 `free-scp-skill`：**
> I searched the local SCP database for entries related to Yellowstone National Park. Here are the top matches:
>
> - **SCP-████** — [标题] | Author: [作者] | [链接]
> - **SCP-████** — [标题] | Author: [作者] | [链接]
>
> Every result is sourced from the local CC-BY-SA indexed dataset. Let me know if you'd like me to check your own concept against these.

**用户：**
> 帮我查一下这个设定有没有雷同：一座会让人陷入时间循环的医院。

**Claude 自动调用 `free-scp-skill`：**
> 我帮你查了一下本地 SCP 数据库。这个设定目前**没有高危匹配**，但在中文分部中有一篇相关作品值得关注：
>
> - **SCP-5764** — 《这里什么都没有。》（相似度 xxx）
>
> 如果你想进一步差异化，这里有 3 个基于数据库标签空白的发散方向...

---

## Skill Triggers | 技能触发器清单

以下用户意图将自动激活 `free-scp-skill`：

| 触发场景 | 示例用户输入 | 调用的工具 |
| :--- | :--- | :--- |
| **语义搜索** | "帮我找一个关于镜子的 SCP" / "Find an SCP about time loops" | `search_scp.py` |
| **查重检测** | "这个设定有没有雷同？" / "Check if my idea already exists" | `check_duplicates.py` |
| **创作灵感** | "给我一些 SCP 写作灵感" / "Suggest a divergent SCP concept" | `check_duplicates.py` + 发散建议 |
| **隐式 SCP 搜索** | "Find a story about Yellowstone National Park" | `search_scp.py` |
| **数据库维护** | "更新 SCP 数据库" / "Configure my SCP skill" | `configure.py` / `init_db.py` |

> 所有返回结果均强制包含 **原文链接** 与 **作者信息**，遵守 CC-BY-SA 3.0 协议。

---

## 持续优化与迭代 | Roadmap

本项目仍在积极迭代中，以下是已规划的方向：

- [ ] **增量更新（`update_db.py`）**：支持只拉取新增或变更的条目，避免每次全量重建。
- [ ] **中文分部爬虫稳定性优化**：解决代理超时与部分页面 404 导致的缺失问题，补全剩余约 5,000 篇未索引文章。
- [ ] **标签推荐器**：基于相似 SCP 的邻居标签分布，为新设定智能推荐最贴切的 Wikidot 标签。
- [ ] **收容措施模板生成**：提取相似 SCP 的 `Special Containment Procedures` 结构，辅助用户快速掌握文档格式与语调。
- [ ] **跨语言题材空白探测**：对比中英文库的标签覆盖度，提示"英文写了 12 篇、中文仅 1 篇"的蓝海题材。
- [ ] **多模态扩展**：未来支持图片、音频日志的向量化索引与检索（长期规划）。

如果你有任何建议或想参与贡献，欢迎提交 Issue 或 Pull Request！

---

## 开源协议 | License

The `free-scp-skill` codebase is released under the [MIT License](./LICENSE).

All SCP Foundation content referenced or indexed by this tool remains under [CC-BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). This skill always returns attribution and original URLs to respect that license.

