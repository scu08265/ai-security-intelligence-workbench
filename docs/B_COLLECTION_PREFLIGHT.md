# B 任务首次真实采集 · 只读预检报告

| 项 | 值 |
| --- | --- |
| 报告范围 | 仅 B 任务：第一次真实采集前的只读预检 |
| 生成日期 | 2026-09-30 |
| 基线 | 分支 `feat/b-evaluation` @ `3dc91b1` |
| 检查方式 | 静态代码/配置阅读 + 不产生副作用的只读探测 |

## 0. 效力边界

本次预检**未发起任何外部网络请求**、**未运行任何采集命令或定时任务**、**未创建 `data/`**、**未修改数据库**、**未安装依赖**、**未读取或输出任何密钥值**。

唯一的"执行"动作是两次只读探测：一次导入 `app.config` 观察路径解析（确认未创建目录），一次用临时目录里的假 `.env` 文件验证 `load_env_file()` 的生效顺序（临时文件在 `%TEMP%`，已删除）。仓库工作区未因此产生任何文件。

### 本次检查过的路径

```
app/config.py                    app/storage.py
app/agents.py                    app/collectors/__init__.py
app/collectors/vuln.py           app/collectors/knowledge.py
app/observability.py             app/paper_fulltext.py
app/scheduled_job.py             app/sources.py
tools/run_collection.py          tools/run_scheduled_collection.py
scripts/run_scheduled_collection.ps1  scripts/backup_database.ps1
scripts/restore_database.ps1     .env.example   .gitignore
```

---

## A. 独立数据目录

### A.1 `INTEL_DATA_DIR` 的读取方式（已确认）

`app/config.py`：

| 行号 | 内容 |
| --- | --- |
| 14 | `BASE_DIR = Path(__file__).resolve().parent.parent` |
| **25** | `DATA_DIR = Path(os.getenv("INTEL_DATA_DIR") or (BASE_DIR / "data"))` |
| 26 | `SNAPSHOT_DIR = DATA_DIR / "snapshots"` |
| 27 | `DB_PATH = DATA_DIR / "intel.sqlite"` |
| 29 | `ENV_FILE = BASE_DIR / ".env"` |
| **117** | `load_env_file()`（模块末尾才调用） |

三个路径全部由同一个 `DATA_DIR` 派生，没有第二处独立定义。

### A.2 ⚠️ 关键限制：`.env` 里的 `INTEL_DATA_DIR` 不生效（已实测）

`DATA_DIR` 在第 25 行求值，而 `load_env_file()` 在第 117 行才被调用。模块级常量一旦求值就不再变化，因此**写在 `.env` 里的 `INTEL_DATA_DIR` 不会改变数据目录**。

实测（在临时目录造了一个含 `INTEL_DATA_DIR` 的假 `.env`，然后调用真实的 `config.load_env_file()`）：

```
import 后 config.DATA_DIR      = D:\ICT\ai-security-intelligence-workbench-git\data
import 后 os.environ 中该键    = None
load_env_file 之后 os.environ  = 'D:\\ICT\\_from_dotenv_should_be_ignored'
load_env_file 之后 DATA_DIR    = D:\ICT\ai-security-intelligence-workbench-git\data
结论: .env 里的 INTEL_DATA_DIR 是否改变 DATA_DIR -> False
```

**结论：必须把 `INTEL_DATA_DIR` 设为真实进程环境变量，不能用 `.env`。**

补充：`os.getenv("INTEL_DATA_DIR") or (BASE_DIR/"data")` 意味着**空字符串会回落到默认目录**。

### A.3 采集调用链确实使用该配置（已确认）

| 环节 | 代码位置 | 是否走 `config.DATA_DIR` |
| --- | --- | --- |
| SQLite | `app/storage.py::connect()` → `sqlite3.connect(config.DB_PATH)` | ✔ |
| 目录创建 | `connect()` 开头调用 `config.ensure_dirs()` → 建 `DATA_DIR` 与 `SNAPSHOT_DIR` | ✔ |
| 快照 | `app/storage.py::save_snapshot` → `config.SNAPSHOT_DIR / source_id / <sha>.<ext>` | ✔ |
| RAG 原文件 | `app/rag_corpus.py`（经 `snapshot_path`） | ✔ |
| arXiv PDF | `app/paper_fulltext.py` → `storage.save_snapshot("arxiv", raw, suffix="pdf")` | ✔ |
| CLI 证据文件 | `tools/run_collection.py`：`default=config.DATA_DIR / "evidence" / "collection_runs.jsonl"` | ✔ |
| 结构化日志 | `app/observability.py`：`config.DATA_DIR / "logs" / ...` | ✔（但该 CLI 路径不会触发，见 D.3） |

实测（只读导入，未创建目录）：

```
INTEL_DATA_DIR = D:\ICT\_preflight_probe_nonexistent_dir
config.DATA_DIR      = D:\ICT\_preflight_probe_nonexistent_dir
config.SNAPSHOT_DIR  = D:\ICT\_preflight_probe_nonexistent_dir\snapshots
config.DB_PATH       = D:\ICT\_preflight_probe_nonexistent_dir\intel.sqlite
目录是否已存在: False

未设置 env 时：config.DATA_DIR = D:\ICT\ai-security-intelligence-workbench-git\data
```

### A.4 会绕过该配置的路径（已确认，仅报告，不修改）

全仓库搜索 `BASE_DIR` 与硬编码 `"data"` 的结果：

| 位置 | 内容 | 是否影响 B 任务采集 |
| --- | --- | --- |
| `app/agents.py:377` | `config.BASE_DIR / "research" / "cases.json"` | 否（只读） |
| `app/evaluation.py:113` | `config.BASE_DIR / "research" / "cases.json"` | 否（只读） |
| `scripts/backup_database.ps1:8` | `$DataDir = Join-Path $Root "data"` | **会**：硬编码 `data`，忽略 `INTEL_DATA_DIR` |
| `scripts/restore_database.ps1:8` | `Join-Path $Root "data\intel.sqlite"` | **会**：同上 |
| `scripts/run_scheduled_collection.ps1:10` | `Join-Path $Root "artifacts\logs"` | 日志写到仓库 `artifacts/`，不在数据目录内 |

以上三个脚本均属 **A 任务产物**，本次采集**不打算调用**。仅在"有人误跑备份/还原脚本"时才有影响；备份脚本会把**默认 `data/`** 当作数据源，而还原脚本会把文件写回默认 `data/`。

`app/` 与 `tools/` 下**没有**绕过 `config.DATA_DIR` 的写入路径。

### A.5 推荐的 Windows 环境变量设置方式（仅展示，未执行）

```powershell
# 方式一：命令行前置（最直白，PyCharm 之外推荐）
$env:INTEL_DATA_DIR = "D:\ICT\intel-data-b"
cd D:\ICT\ai-security-intelligence-workbench-git
.\.venv\Scripts\python.exe tools\run_collection.py --sources <见 B.1> --enrich-limit 0

# 方式二：只对该次进程生效，不改动当前会话
$env:INTEL_DATA_DIR = "D:\ICT\intel-data-b"; .\.venv\Scripts\python.exe tools\run_collection.py ...
```

PyCharm 场景：**Run/Debug Configurations → Environment variables** 里加 `INTEL_DATA_DIR=D:\ICT\intel-data-b`（不要写进 `.env`）。

**不要**把 `INTEL_DATA_DIR` 写进项目根目录的 `.env`——已实测无效（见 A.2）。

### A.6 目录配置完整性结论

配置本身**完整**：SQLite、snapshots、evidence、logs 全部由 `config.DATA_DIR` 派生，采集链路全部走该配置。唯一缺陷是 **`.env` 对该键无效**，属使用方式限制而非代码缺陷；另有 3 个 A 任务脚本硬编码默认 `data/`。

---

## B. 来源选择

### B.1 CLI 准确写法（仅展示，未执行）

`tools/run_collection.py` 的 `--sources` 是**逗号分隔**的已登记 `source_id`，会用 `agents.sources.BY_ID` 校验，未登记 id 直接 `parser.error` 退出。

注意：该脚本自带的 `DEFAULT_SOURCES` 只有 **6 个**（`cisa_kev,openalex,owasp_genai,nist_ai_rmf,mitre_atlas,eu_ai_act`），**不等于** 12 个推荐来源。要覆盖 12 + arXiv 必须显式传参：

```powershell
.\.venv\Scripts\python.exe tools\run_collection.py `
  --sources nvd,mitre_cve,osv,cisa_kev,msrc,security_blog,openalex,owasp_genai,nist_ai_rmf,mitre_atlas,eu_ai_act,nist_news,arxiv `
  --enrich-limit 0
```

**`--enrich-limit 0` 不是可选项，是必需项**，原因见 B.3。

### B.2 `ghsa` 缺少 `GITHUB_TOKEN` 时的真实行为（已确认）

`app/collectors/__init__.py::collect()` 在调用收集器**之前**检查令牌：

```
if spec.requires_token_env and not os.getenv(该变量).strip():
    return CollectOutcome(status="skipped",
                          error="缺少环境变量 GITHUB_TOKEN，未尝试采集（不以空结果冒充成功）")
```

- 行为：**直接返回 `skipped`，不发起任何请求**，不产生事件，不写快照。
- 对其他来源的影响：**无**。`_run_collection_deterministic` 的 `for source_id in selected` 循环继续执行下一个来源。
- 副作用：`skipped` 会被计入 `degraded`，因此**整体 run 状态会变成 `partial`**（而不是 `completed`）。CLI 退出码仍为 0（`partial` 被接受）。
- `source_state` 会被写成 `status="skipped"`，`last_error` 记录该提示文本，`events_count` 统计既有事件数。

### B.3 是否存在隐式启用（已确认，含一处陷阱）

| 可能被隐式启用的动作 | 结论 |
| --- | --- |
| `close_gaps`（采集时逐条补证） | **默认关闭**。`--close-gaps` 是 `store_true`，`run_collection(close_gaps=False)` |
| **采集后富化** | ⚠️ **默认开启**。`tools/run_collection.py` 在采集后无条件执行 `agents.run_enrichment(limit=args.enrich_limit)`，而 `--enrich-limit` **默认值是 6**。必须显式传 `--enrich-limit 0` 才能关闭 |
| 资产研判 | **不会**。`run_assessment()` 未被该 CLI 调用 |
| 定时任务 / 自愈 | **不会**。`app/scheduled_job.py`、`self_healing` 只在 `tools/run_scheduled_collection.py` 路径上触发 |

富化的代价：`run_enrichment` 对每条事件调用 `close_evidence_gaps`，该函数在 `MAX_ROUNDS=2`、`TOOL_BUDGET=3` 预算内调用补证工具，而这些工具**会真实发起网络请求**：

| 工具 | 端点 |
| --- | --- |
| `tool_nvd` | `https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=...` |
| `tool_mitre` | `https://cveawg.mitre.org/api/cve/{cve_id}` |
| `tool_osv` | `https://api.osv.dev/v1/vulns/{candidate}`（会遍历 id 与别名） |
| `tool_kev` | `https://www.cisa.gov/.../known_exploited_vulnerabilities.json` — **每次调用都重新下载整个 KEV 目录** |

按默认 `--enrich-limit 6` 估算，最多新增 6 条事件 × 6 次工具调用 = **36 次额外请求**，且每个 KEV 工具调用都是全量下载。这些请求的快照写到 `snapshots/tool_nvd`、`tool_mitre`、`tool_osv`、`tool_kev` 四个额外子目录。

### B.4 第一轮将访问的端点、请求预算与预期写入（已确认）

以下为**不含重试**的基准请求数（每个可重试失败最多再尝试 3 次，退避 1/2/4 秒）。

| 来源 | 冷启动请求数 | 端点 | 预期写入 |
| --- | --- | --- | --- |
| `nvd` | 1–2（上限 2 页 × 200） | `services.nvd.nist.gov` | `snapshots/nvd/<sha>.json` |
| `mitre_cve` | **0（预计 skipped）** | — | — |
| `osv` | ≤13（1 次批量 + ≤12 次详情） | `api.osv.dev` | `snapshots/osv/<sha>.json` |
| `cisa_kev` | 1 | `www.cisa.gov` | `snapshots/cisa_kev/<sha>.json` |
| `msrc` | 2（索引 + 最新文档） | `api.msrc.microsoft.com` | `snapshots/msrc/<sha>.json` |
| `security_blog` | 1 | `github.blog` | `snapshots/security_blog/<sha>.xml` |
| `openalex` | 1 | `api.openalex.org` | `snapshots/openalex/<sha>.json` |
| `owasp_genai` | 1 | `genai.owasp.org` | `snapshots/owasp_genai/<sha>.html` |
| `nist_ai_rmf` | 1 | `www.nist.gov` | `snapshots/nist_ai_rmf/<sha>.html` |
| `mitre_atlas` | 1 | `atlas.mitre.org` | `snapshots/mitre_atlas/<sha>.html` |
| `eu_ai_act` | 1 | `data.consilium.europa.eu` | `snapshots/eu_ai_act/<sha>.pdf` |
| `nist_news` | 1 | `www.nist.gov` | `snapshots/nist_news/<sha>.xml` |
| `arxiv` | ≤6（1 次查询 + ≤5 篇 PDF） | `export.arxiv.org`、`arxiv.org` | `snapshots/arxiv/<sha>.xml` 与 `<sha>.pdf` |

合计（不含重试、不含富化）：**约 18–27 次请求**。

若误用默认 `--enrich-limit 6`，再叠加最多 36 次请求。

**可能下载的 PDF**：`eu_ai_act` 官方 PDF（1 份，较大）+ arXiv 全文 PDF（最多 5 份），全部落在 `snapshots/` 下。

`mitre_cve` 冷启动为何预计跳过：`_cve_candidates()` 只从**库内已有事件**中挑 `CVE-` 前缀且尚无 MITRE 来源的记录；首次运行时库为空，因此返回空列表并把状态置为 `skipped`，提示"需先由其它来源发现"。

---

## C. 首次运行风险

### C.1 是否会覆盖 / 重置 / 删除（已确认：不会）

| 风险 | 结论 | 依据 |
| --- | --- | --- |
| 建表时清空数据库 | **不会** | `SCHEMA` 全部是 `CREATE TABLE/INDEX/TRIGGER IF NOT EXISTS`，无 `DROP` |
| 覆盖已有事件 | 仅同 `id` 更新 | `upsert_event` 使用 `ON CONFLICT(id) DO UPDATE`；`id` 是稳定标识（CVE/GHSA/PYSEC/arXiv/OPENALEX） |
| 覆盖已有快照 | **不会** | `save_snapshot` 内容寻址 + `if not path.exists()` |
| 删除记录 | **不会** | 采集链路无 DELETE；全仓库仅 `delete_asset`（用户主动）与 `clear_assessments`（**无调用点**） |
| 重置 cursor | 仅按正常增量推进 | 见 C.2 |

### C.2 源游标与冷启动时间窗口（已确认）

数据库为空时 `storage.source_state(source_id)` 返回默认值，其中 **`cursor = None`**。`collect(source_id, since=None)` 会把 `None` 传给各收集器，由各收集器回落到自己的默认窗口：

| 来源 | 冷启动窗口 |
| --- | --- |
| `nvd` | 最近 **7 天**，再向前扩 6 小时重叠 |
| `openalex` | 最近 **30 天** |
| `security_blog`、`nist_news` | 最近 **30 天** |
| `arxiv` | 最近 **14 天** |
| `osv` | `cutoff=None` → 视为全部命中，取最新 12 条详情 |
| `cisa_kev` | `cutoff=None` → **遍历整个目录**（按 `ai_relevance` 过滤后入库） |
| `msrc` | 最新 1 份月度文档 |
| `owasp_genai` / `nist_ai_rmf` / `mitre_atlas` | 无窗口，按内容哈希判断是否变化 |
| `eu_ai_act` | 无窗口，单次下载 |
| `mitre_cve` | 无候选 → skipped |

游标写回条件：`if outcome.cursor and outcome.ok` 才更新。因此**成功或部分成功后游标前进**，下次即为增量；失败不推进游标。

**冷启动影响**：第一轮会一次性纳入上述窗口内的全部条目，事件数会明显多于后续增量；时效分布也会偏低（A 任务已观察到 `≤24h` 比例很低）。

### C.3 独立目录首次运行的初始化行为（已确认）

`tools/run_collection.py` 第一步就是 `storage.init_db()`，而 `storage.connect()` 开头调用 `config.ensure_dirs()`，因此**首次运行会依次创建**：

1. `<INTEL_DATA_DIR>/`
2. `<INTEL_DATA_DIR>/snapshots/`
3. `<INTEL_DATA_DIR>/intel.sqlite`（连同 `intel.sqlite-wal`、`intel.sqlite-shm`，因为 `PRAGMA journal_mode=WAL`）
4. 各来源快照子目录 `<INTEL_DATA_DIR>/snapshots/<source_id>/`
5. `<INTEL_DATA_DIR>/evidence/collection_runs.jsonl`（由 CLI 的 `--output` 默认值创建父目录并追加）

**不会**创建 `<INTEL_DATA_DIR>/logs/`：`observability.log_event` 只在 `api.py`、`scheduled_job.py`、`self_healing.py`、`run_scheduled_collection.py` 中被调用，本 CLI 路径不触发。

### C.4 写入路径汇总（独立目录场景）

```
<INTEL_DATA_DIR>/
├── intel.sqlite              (+ -wal / -shm)
├── snapshots/
│   ├── nvd/  mitre_cve/  osv/  cisa_kev/  msrc/  security_blog/
│   ├── openalex/  owasp_genai/  nist_ai_rmf/  mitre_atlas/
│   ├── eu_ai_act/  nist_news/  arxiv/
│   └── tool_nvd/ tool_mitre/ tool_osv/ tool_kev/   ← 仅在启用富化时出现
└── evidence/collection_runs.jsonl
```

### C.5 失败处理（已确认）

| 情形 | 行为 |
| --- | --- |
| 缺少必需令牌 | `skipped`，附明确原因，不冒充成功 |
| 上游 4xx/5xx 或网络异常 | `FetchError` → `status="failed"` + 真实错误文本；可重试状态会先重试 |
| 有历史数据但本次失败 | 状态升级为 `stale`（区别于 `failed`） |
| 单来源达到分页/预算上限 | `status="partial"` + notes 说明截断范围 |
| 整体状态 | 全部失败 → `failed`；任一 `failed/partial/skipped` → `partial`；否则 `completed` |
| CLI 退出码 | `completed`/`partial` → 0；否则 1 |
| 单来源异常 | 被 `collect()` 捕获并转为该来源的失败结果，**不中断其他来源** |

---

## D. 输出与推荐命令

### D.1 本报告文件

`docs/B_COLLECTION_PREFLIGHT.md`（本文件）。写入前已确认同名文件**不存在**，未覆盖任何内容。

### D.2 推荐命令（仅展示，未执行）

```powershell
# 1) 设定独立数据目录（必须用真实环境变量，不能写 .env）
$env:INTEL_DATA_DIR = "D:\ICT\intel-data-b"

# 2) 12 个推荐来源 + arxiv，关闭采集后富化
cd D:\ICT\ai-security-intelligence-workbench-git
.\.venv\Scripts\python.exe tools\run_collection.py `
  --sources nvd,mitre_cve,osv,cisa_kev,msrc,security_blog,openalex,owasp_genai,nist_ai_rmf,mitre_atlas,eu_ai_act,nist_news,arxiv `
  --enrich-limit 0

# 3) 核对结果（只读）
.\.venv\Scripts\python.exe -c "import sys;sys.path.insert(0,'.');from app import storage;print(storage.list_runs(limit=3))"
```

不加入 `ghsa`（缺令牌会 `skipped` 并把整体状态拉成 `partial`）；若你决定提供令牌，再把它追加到 `--sources`。

### D.3 尚未解决 / 需要实测确认的风险

| # | 风险 | 类型 |
| --- | --- | --- |
| 1 | 网络出口可达性未验证（按要求未发请求）。A 任务文档记载 arXiv 曾返回 HTTP 406 | 需实测 |
| 2 | `mitre_cve` 首次运行预计 `skipped`（库内无 CVE 候选），会使状态为 `partial` | 已确认（静态） |
| 3 | `--enrich-limit` 默认 6，误用会显著增加外网请求与快照目录 | 已确认 |
| 4 | `.env` 中的 `INTEL_DATA_DIR` 无效 | 已实测 |
| 5 | `scripts/backup_database.ps1`、`restore_database.ps1` 硬编码默认 `data/`，若误跑会指向另一目录 | 已确认（静态） |
| 6 | WAL 模式会产生 `-wal` / `-shm` 旁文件，拷贝目录时需一并处理 | 已确认（静态） |
| 7 | POC 维度很可能结构性为 0（无专门采集器），影响富化金标准第六维度 | 已知 |
| 8 | 冷启动窗口大，首次事件数偏多、时效偏低 | 已确认 |
| 9 | 采集耗时不可预估：仅 KEV 全量目录 + arXiv 最多 5 篇 PDF 就可能有数分钟 | 需实测 |
| 10 | 磁盘占用不可预估：EU AI Act PDF 与 arXiv PDF 体积未知 | 需实测 |

### D.4 结论

独立数据目录的配置链路**完整可用**，唯一使用限制是必须用真实环境变量而非 `.env`。首次运行**不会覆盖、重置或删除**任何既有数据。除 `mitre_cve` 预计跳过、以及必须显式关闭采集后富化之外，没有发现阻塞性问题。

**本报告完成后暂停，等待审查后再决定是否批准真实采集。**

---

## 附录 · 本次未做的事

- 未发起任何外部网络请求，未运行任何采集命令或定时任务
- 未创建 `data/`，未创建 `.env`，未修改数据库
- 未安装依赖
- 未修改任何既有代码或配置文件；`docs/B_COLLECTION_PREFLIGHT.md` 是本阶段唯一新增文件
- 未执行任何 git 写操作（无 add / commit / push / merge / rebase / 分支切换）
- 未读取、未输出任何密钥或令牌值
