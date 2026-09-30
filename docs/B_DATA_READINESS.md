# B 任务数据就绪性报告

| 项 | 值 |
| --- | --- |
| 报告范围 | 仅 B 任务：真实采集流程梳理 + 两类评测素材的数据需求 |
| 生成日期 | 2026-09-30 |
| 基线 | 分支 `feat/b-evaluation` @ `3dc91b1` |
| 检查方式 | 纯静态代码/配置/文档阅读 + 对仓库内既有产物的只读解析 |

## 0. 说明与本报告的效力边界

- 本报告**没有发起任何外部网络请求**，**没有运行任何采集命令或定时任务**，**没有修改数据库或 `data/`**。
- 下文凡标注「已确认」的结论，均可在本节末尾列出的代码路径中逐行核对；标注「需实测确认」的，属于静态阅读无法定论、必须实际运行才能验证的推断。
- 报告内不包含、也未读取任何密钥或令牌值。当前克隆环境中**不存在 `.env`**，因此没有可泄露的凭据。

### 本次实际检查过的路径

```
app/config.py                      app/sources.py
app/collectors/__init__.py         app/collectors/vuln.py
app/collectors/knowledge.py        app/agents.py
app/storage.py                     app/provenance.py
app/normalize.py                   app/dedupe.py
app/paper_fulltext.py              app/rag_corpus.py
app/scheduled_job.py               app/observability.py
app/multi_agent_runtime.py         app/self_healing.py
tools/run_collection.py            tools/run_scheduled_collection.py
scripts/run_scheduled_collection.ps1   scripts/crontab.example
.github/workflows/ci.yml           .env.example   .gitignore
reports/latency-summary.json       reports/source-health.json
reports/7-day-continuous-run-report.md  reports/daily-logs/*.json
```

---

## 1. 采集入口与调用链

### 1.1 四个入口（已确认）

| 入口 | 触发方式 | 位置 |
| --- | --- | --- |
| 单次采集 CLI | `python tools/run_collection.py --sources <ids>` | `tools/run_collection.py` |
| 计划任务 CLI | `python tools/run_scheduled_collection.py --task-id ...` | `tools/run_scheduled_collection.py` → `app/scheduled_job.py` |
| HTTP 接口 | `POST /api/collect`（可带 `source_ids`） | `app/api.py` |
| 流式全流程 | `POST /api/stream/pipeline` | `app/api.py` → `app/streaming.py` |
| 外部调度封装 | Windows Task Scheduler / cron | `scripts/run_scheduled_collection.ps1`、`scripts/crontab.example`、`scripts/install_windows_task.ps1` |

另有一个**非网络**入口：`POST /api/seed`，只读本地 `research/cases.json` 并写库（核验案例 + 合成演示资产），不属于采集。

### 1.2 调用链（已确认）

```
入口
└─ agents.run_collection(source_ids, close_gaps=False, trigger=..., scheduler=...)
   ├─ 未指定 source_ids 时使用 sources.recommended_sources()
   ├─ agent_orchestration.collection_plan(valid_ids, config.model_config() or None)
   └─ agents._run_collection_deterministic(requested, ...)
      └─ 对每个 source_id:
         ├─ state = storage.source_state(source_id)          # 增量游标
         ├─ collectors.collect(source_id, since=state["cursor"])
         │  ├─ 若 spec.requires_token_env 未设置 → status="skipped"（不冒充成功）
         │  ├─ 分发到 collectors.vuln.* 或 collectors.knowledge.*
         │  │  ├─ http_request(...)                          # httpx + 重试退避
         │  │  ├─ record_snapshot → storage.save_snapshot     # 原始字节落盘
         │  │  └─ normalize.<source>_to_event → ai_relevance 判定
         │  └─ 返回 CollectOutcome(fetched/filtered/events/notes/cursor)
         ├─ 对每个事件: agents.process_and_store(event)
         │  ├─ process_event（可选 close_evidence_gaps）
         │  ├─ dedupe.resolve  → new | updated | merged | unchanged
         │  ├─ provenance.mark_ingested
         │  └─ storage.upsert_event
         ├─ arXiv 专属: paper_fulltext.ingest_arxiv_paper（限 arxiv.org，每轮预算 5 篇）
         └─ storage.update_source_state(source_id, status/last_run/last_success/
                                        last_error/events_count/cursor/last_hash)
      └─ storage.save_run(kind="collect", status, detail{results, timeliness, tool_calls, trigger, scheduler})
```

`app/scheduled_job.py::run_scheduled_collection` 在标准采集之外额外做三件事（属 A 任务）：先 `refresh_source_event_counts()`、失败或部分成功时调用 `self_healing.run_self_healing(...)`、并写 `observability` 日志与告警。

### 1.3 收集器的实际实现范围（已确认）

| 分发键 | 实现位置 | 覆盖的来源 |
| --- | --- | --- |
| `nvd` `mitre_cve` `osv` `ghsa` `cisa_kev` `msrc` | `app/collectors/vuln.py` | 6 个漏洞库/公告源 |
| `arxiv` `openalex` `rss` `page` `document` | `app/collectors/knowledge.py` | 论文、博客、标准页、政策 PDF |
| `agent` | 未在 `_load_collectors()` 中注册 | 仅为规划器保留的动作名，无对应收集器 |

> 注：`app/multi_agent_runtime.py` 中的 `WorkerAgent` 使用**注入式**执行器（构造时传入 callable），本身不直接发起网络请求；`POST /api/agent/multi/execute` 需要调用方提供动作实现。这一点与采集链路是分开的。

---

## 2. 数据来源及请求范围

### 2.1 登记来源（已确认，共 14 个）

来源表在 `app/sources.py::SOURCES` 中硬编码。`recommended_sources()` 返回其中 `auto_default=True` 的 **12 个**。

| id | 类别 | 模式 | 自动 | 需令牌 | 端点 |
| --- | --- | --- | --- | --- | --- |
| `nvd` | CVE/NVD 官方漏洞库 | api | ✔ | — | `https://services.nvd.nist.gov/rest/json/cves/2.0` |
| `mitre_cve` | CVE 权威记录 | api | ✔ | — | `https://cveawg.mitre.org/api/cve` |
| `osv` | 开源生态漏洞库 | api | ✔ | — | `https://api.osv.dev/v1/querybatch` |
| `ghsa` | 安全社区与聚合公告 | api | ✘ | `GITHUB_TOKEN` | `https://api.github.com/advisories` |
| `cisa_kev` | 在野利用情报 | feed | ✔ | — | `https://www.cisa.gov/.../known_exploited_vulnerabilities.json` |
| `msrc` | 厂商安全公告 | api | ✔ | — | `https://api.msrc.microsoft.com/cvrf/v3.0/updates` |
| `security_blog` | 安全博客与社区 | rss | ✔ | — | `https://github.blog/tag/security/feed/` |
| `arxiv` | 学术论文 | api | ✘ | — | `https://export.arxiv.org/api/query` |
| `openalex` | 学术论文 | api | ✔ | — | `https://api.openalex.org/works` |
| `owasp_genai` | 技术标准与最佳实践 | page | ✔ | — | `https://genai.owasp.org/llmrisk/llm01-prompt-injection/` |
| `nist_ai_rmf` | AI 风险治理框架 | page | ✔ | — | `https://www.nist.gov/itl/ai-risk-management-framework` |
| `mitre_atlas` | AI 威胁知识框架 | page | ✔ | — | `https://atlas.mitre.org/` |
| `eu_ai_act` | 政策法规 | pdf | ✔ | — | `https://data.consilium.europa.eu/doc/document/PE-24-2024-INIT/en/pdf` |
| `nist_news` | 政策法规 | rss | ✔ | — | `https://www.nist.gov/news-events/news/rss.xml` |

### 2.2 网络请求范围（已确认）

- **不接受任意 URL**：API 只接受能在 `sources.BY_ID` 中解析的 `source_id`；`collect()` 对未登记 id 直接返回 `skipped`。前端无 URL 输入框。这是刻意的 SSRF 防护。
- 存在四类**派生请求**，端点由代码固定或由上游索引响应提供，仍然不接收用户输入：

| 来源 | 派生端点 | 约束 |
| --- | --- | --- |
| `osv` | `https://api.osv.dev/v1/vulns/{id}`（硬编码前缀） | id 来自前一次查询结果 |
| `mitre_cve` | `{spec.url}/{cve_id}` | cve_id 来自库内已有事件 |
| `msrc` | `doc["CvrfUrl"]` | 来自 MSRC 官方索引响应 |
| `arxiv` | `https://arxiv.org/pdf/{arxiv_id}` | 主机白名单 `ARXIV_HOSTS = {arxiv.org, www.arxiv.org, export.arxiv.org}` |

- 请求头：默认 `User-Agent: ai-sec-intel/<version> (competition research; +https://localhost)`；`page`/`document` 使用浏览器 UA 与 `Accept-Language`。
- 超时：默认 25 s；NVD 45 s、OSV 批量 60 s、OSV 详情 30 s、MSRC 索引 45 s / 文档 90 s、arXiv 60 s、OpenAlex 60 s、RSS 45 s、页面 45 s、PDF 90 s。
- 重试：`RETRY_STATUS = {406,408,425,429,500,502,503,504,522,524}`；退避 `(1,2,4)` 秒；尊重 `Retry-After`（上限 60 s）；最多 3 次重试（共 4 次尝试）。

### 2.3 时间窗口、分页与预算（已确认）

| 来源 | 窗口 | 分页/预算上限 |
| --- | --- | --- |
| `nvd` | `cursor-6h`，无游标时最近 7 天 | `NVD_MAX_PAGES=2` × `NVD_PAGE_SIZE=200` = 最多 400 条 |
| `mitre_cve` | 无时间窗口（对库内已有 CVE 逐条核验） | `MITRE_BUDGET=10` |
| `osv` | 批量查询 42 个包/生态组合 | 详情 `OSV_DETAIL_BUDGET=12`，并发 6 |
| `ghsa` | `updated>=(cursor-6h)` | 最多 3 页 × 100 |
| `cisa_kev` | 全量目录 + 按 `dateAdded` 与 cursor 过滤 | 单请求 |
| `msrc` | 最新月度 CVRF 文档 | `MSRC_RELEASES=1` |
| `arxiv` | 14 天 | `ARXIV_MAX_RESULTS=40`；全文 `DEFAULT_MAX_PAPERS_PER_RUN=5` |
| `openalex` | 30 天 | `OPENALEX_MAX_RESULTS=50` |
| `security_blog` / `nist_news` | 30 天 | 单请求 |
| `owasp_genai` / `nist_ai_rmf` / `mitre_atlas` | 无窗口，按内容哈希比对 | 单请求 |
| `eu_ai_act` | 无窗口 | 单请求 + 全文解析入库 |

### 2.4 筛选条件（已确认）

- 统一入口 `_keep()`：事件必须满足 `ai_relevance.included == True` 才进入结果，否则计入 `filtered`。
- `msrc` 额外用 `AI_VENDOR_PRODUCTS` 关键词表（Azure OpenAI / Copilot / ONNX / DirectML 等 17 个词）过滤 CVE 标题与产品名。
- `osv` 使用 `OSV_SCOPE`（42 个包/生态）；`arxiv` 使用 `ARXIV_QUERY`（cs.CR/cs.LG/cs.AI + 主题词）；`openalex` 使用 `OPENALEX_QUERY`。
- `cisa_kev` 按 `dateAdded` 与 `since` 比较，窗口外条目只计数不入库。

---

## 3. 本地写入路径与覆盖风险

### 3.1 写入路径（已确认）

| 路径 | 内容 | 写入方 | 覆盖语义 |
| --- | --- | --- | --- |
| `$INTEL_DATA_DIR/intel.sqlite` | events、event_aliases、source_state、assets、assessments、runs、duplicate_candidates、rag_*、agent_* | `app/storage.py` | `CREATE TABLE/INDEX/TRIGGER IF NOT EXISTS`，**Schema 中没有任何 DROP** |
| `$INTEL_DATA_DIR/snapshots/<source_id>/<sha256>.<ext>` | 原始响应字节 | `storage.save_snapshot` | 内容寻址；`if not path.exists()` 才写；**永不删除** |
| `$INTEL_DATA_DIR/logs/workbench.jsonl`、`alerts.jsonl` | 结构化日志与告警 | `app/observability.py::_append` | 追加 |
| `$INTEL_DATA_DIR/evidence/collection_runs.jsonl` | CLI 采集逐来源证据 | `tools/run_collection.py` | 追加 |
| `artifacts/logs/scheduled-collection.log` | 计划任务输出 | `scripts/run_scheduled_collection.ps1` | 追加 |

默认 `INTEL_DATA_DIR = BASE_DIR/data`（`app/config.py`），`ensure_dirs()` 会创建 `data/` 与 `data/snapshots/`。

`.gitignore` 已忽略：`data/*.sqlite*`、`data/snapshots/`、`data/evidence/`、`data/logs/`、`artifacts/logs/`、`artifacts/backups/`、`.env`。

### 3.2 覆盖与删除风险（已确认）

全仓库检索 `DELETE FROM` / `DROP TABLE` / `rmtree` / `unlink(` / `Remove-Item`，命中如下：

| 位置 | 语句 | 触发条件 |
| --- | --- | --- |
| `app/storage.py:611-612` | `DELETE FROM assets` + `DELETE FROM assessments` | 仅由 `delete_asset(asset_id)` 触发，即用户主动调用 `DELETE /api/assets/{id}` |
| `app/storage.py:680` | `DELETE FROM assessments` | `clear_assessments()`；**经检索，全仓库只有定义，没有任何调用点** |
| `scripts/backup_database.ps1:34` | `Remove-Item -Force` | 备份脚本内部（A 任务产物），与采集无关 |

**结论**：采集流程**不会删除**任何事件、快照或运行记录。唯一的"覆盖"是 `upsert_event` 对相同 `id` 的 `ON CONFLICT DO UPDATE`——这是设计内的增量更新，`id` 来自稳定标识（CVE/GHSA/PYSEC/arXiv/OPENALEX），不是随机值。

### 3.3 共享环境风险

- 若多人共用同一 `INTEL_DATA_DIR`，采集会写入同一 DB 与快照目录。写入形式是追加/更新，**不删除**，但仍会改变 `source_state.cursor`，从而影响其他人后续增量窗口的起点。
- 本克隆**没有 `data/` 目录**，首次采集将新建。
- 建议用 `INTEL_DATA_DIR` 指向独立目录来做 B 任务的素材采集，避免与 A 任务的每日调度互相干扰（这一点需要你确认，见第 8 节）。

---

## 4. 可复用数据清单

### 4.1 仓库内已有产物（已确认）

| 产物 | 位置 | 可复用性 | 说明 |
| --- | --- | --- | --- |
| 时延记录 | `reports/latency-summary.json` | **部分可复用** | 91 条**事件级**记录，字段：`event_id / source_id / published_at / discovered_at / latency_seconds / latency_hours / valid / unknown_reason` |
| 来源健康 | `reports/source-health.json` | 部分可复用 | 14 个来源的 `events_count / attempts / success_rate / duration_ms_p50 / duration_ms_p95 / current_status / health_class` |
| 每日运行日志 | `reports/daily-logs/2026-09-27.json`、`2026-09-28.json` | 部分可复用 | 每日 `scheduled_runs`（含 run id、状态、逐来源结果）与 `alerts` |
| 7 天连续运行报告 | `reports/7-day-continuous-run-report.md` | 部分可复用 | 聚合数字（时延分档、来源成功率），无事件正文 |
| 运行截图 | `docs/screenshots/`（5 张） | 可复用 | 视觉素材，非数据 |
| SBOM 样例 | `artifacts/sbom/*.json`、`artifacts/simulation/vllm-lab/` | 可复用 | 资产侧素材，可用于任务 4 的策略输入演示 |

### 4.2 从时延报告实测解析出的事件标识分布

对 `reports/latency-summary.json` 的 91 条记录做前缀统计（实测）：

| 前缀 | 条数 |
| --- | --- |
| `CVE-` | 39 |
| `OPENALEX-` | 37 |
| `GHSA-` | 11 |
| `PYSEC-` | 1 |
| `EU_AI_ACT-` | 1 |
| `NIST_AI_RMF-` | 1 |
| `OWASP_GENAI-` | 1 |

其中 `valid=True` 的只有 **1** 条（`CVE-2026-101065`）；其余为 `baseline_backfill_before_monitoring_start` 或 `invalid_or_missing_publisher_time`。

### 4.3 不可复用（已确认）

| 项 | 原因 |
| --- | --- |
| 事件正文（affected / cvss / poc / relationships / conditions） | 报告只保留 ID 与时间戳；数据库 `data/intel.sqlite` 被 `.gitignore` 排除，未提交 |
| 原始快照 | `data/snapshots/` 被 `.gitignore` 排除，未提交 |
| 历史评测产物 | 评测结果写入 DB 的 `runs` 表，随 DB 一起不在仓库中 |
| 关系/攻击链数据 | 现有代码只展示事件内 `relationships`，没有独立关系数据集 |

**净结论**：现有仓库能提供约 **51 个漏洞类事件标识**（39 CVE + 11 GHSA + 1 PYSEC）与 **37 个论文标识**，可以作为"待补全清单"，但**不含任何字段级正文**，因此**无法单独支撑富化金标准**，也无法支撑跨文档/多跳题集。

---

## 5. 问答评测集的数据需求

### 5.1 字段需求

现有 scorer 已定义的字段（`app/eval_dataset.py::score_records`，schema_version `1.0`）：

| 字段 | 用途 | 必需 |
| --- | --- | --- |
| `id` | 题目标识 | ✔ |
| `provenance` | 必须是 `real_verified` 或 `synthetic_regression`（否则 `load_cases` 抛错） | ✔ |
| `source_ref` | 指向核验来源 | ✔ |
| `question` | 题面 | ✔ |
| `expected_event_ids` | 检索期望 | ✔（可为空表示应拒答） |
| `required_answer_terms` | 答案要点 | ✔（可为空） |
| `expected_evidence_ids` | 引用期望 | ✔（可为空） |
| `should_refuse` | 拒答期望 | ✔ |
| `history` | 多轮上下文 | 可选 |

B 任务需要**扩展**的字段（当前不存在）：`category`（六类分型）、`expected_document_ids`（跨文档）、`expected_reasoning_path`（多跳，含边与证据）、`sample_note`（样本局限）。

### 5.2 六类题目所需素材

| 类型 | 需要的素材 | 当前可得性 |
| --- | --- | --- |
| 基础问答 | 已入库漏洞事件（CVE/GHSA）+ 可检索的 title/summary/component | 需真实采集 |
| 语义问答 | 同义改写、中英混合查询 + 对应事件集 | 需人工出题（素材来自采集） |
| 多轮问答 | 历史轮次 + 指代目标（事件/资产） | 合成夹具可造；真实场景需采集 |
| 跨文档 | ≥2 个独立知识对象（文档/事件）+ 各自证据 ID | 需采集 HTML/XML/PDF 入 RAG；**JSON 类型来源按设计不入 RAG** |
| 多跳推理 | 关系边 + 路径 + 每条边的证据 ID | **当前无关系数据**，必须采集后另行构造 |
| 拒答 | 无答案 / 越界问题 | 可合成 |

### 5.3 核验方式

- **标准答案**：由来源原文核对。`research/cases.json` 已有三级证据等级字段 `evidence_grade`（如 `official_project_advisory`、`authoritative_database_cross_checked_with_official_repository`），可作为核验强度的参照。
- **证据 ID**：由 `normalize._source_id(prefix, payload)` 生成，规则是 `f"{prefix}:{sha256(payload)[:10]}"`，**对同一 payload 可复现**，因此可以作为稳定引用。
- **引用依据**：落 `source_ref` 指向 `research/cases.json#<id>` 或原始 URL。
- **拒答预期**：`should_refuse` 显式标注，`true` 表示必须拒答。

### 5.4 避免空库/空检索产生误导性指标

已在本任务审计中实测过两个具体风险（见 `docs/B_TASK_AUDIT.md` 风险 B-02 / B-03）：

1. **空库下 `retrieval_precision` 返回 1.0**（`tp=1, fp=0`），而同份结果 `retrieval_recall` 仅 0.3333。
2. **空库下平均响应 0.137 ms**，是"未检索到证据"的耗时，不能用于对照 `≤5s`。

因此需要两道守卫：

- **语料守卫**：`storage.list_events()` 为空或低于阈值时，评测直接返回「不可评测」，不输出任何准确率与耗时。
- **分母守卫**：每个指标声明最小样本数；低于下限时同样报「不可评测」，而不是给出看似满分的数值。

---

## 6. 富化金标准的数据需求

### 6.1 标注条目字段建议

```
relation_id        稳定主键（建议 dimension + event_id + 判别依据 的哈希）
event_id           必须使用稳定 ID（CVE / GHSA / PYSEC / arXiv / OPENALEX），不用数据库自增 ID
dimension          paper_link | version_range | fixed_version | cvss | poc | asset_assessment
subject            关系主体（如 package / component / event id）
object             关系客体（如论文 ID / 版本区间 / 修复版本 / CVSS 向量 / POC URL）
expected_verdict   positive | negative | unknown
source_url         核验依据的原始链接（必填）
source_publisher   发布方
evidence_grade     参照 research/cases.json 的等级字段
verified_by        核验人
verified_at        核验时间
notes              局限说明
```

### 6.2 六个维度各自需要的真实素材

| 维度 | 需要的素材 | 可提供的来源 | 当前可得性 |
| --- | --- | --- | --- |
| 论文关联 | 漏洞事件 ↔ 论文（标题 / arXiv ID / DOI / URL） | `arxiv`、`openalex` | 需采集 |
| 版本范围 | `affected[].range` + `package` + `ecosystem` | `nvd`、`osv`、`ghsa`、`mitre_cve` | 需采集 |
| 修复版本 | `affected[].fixed_version` | 同上 | 需采集 |
| CVSS | `cvss[].score` / `vector` / `source_id` | `nvd`、`osv`、`msrc`、`ghsa` | 需采集 |
| POC 状态 | `poc[].url` / `status` / `source_id` | 现有来源中只有 `ghsa` 的 references 与 `cisa_kev` 的利用证据间接相关 | **风险：源码中没有任何专门的 POC 采集器** |
| 资产关联 | 事件 × 资产判定 + `reasons` + `evidence_ids` | 本地 `intelligence.assess_asset` | 依赖资产；演示资产可合成，真实资产需用户提供 |

> POC 维度需要特别注意：`app/collectors/` 下没有针对 POC 的采集逻辑；`normalize` 中的 `poc` 字段依赖来源是否在公告里自带引用。因此在当前来源组合下，该维度很可能**结构性接近 0**，且与标注质量无关。这一点必须在报告中如实呈现，不能通过修改判定口径提高数值。

### 6.3 正例 / 负例 / 未知的划分

- **positive**：来源明确记录该关系成立，且有可打开的原文。
- **negative**：来源明确记录了相反事实（例如"该版本不在受影响区间""该 CVE 不涉及此组件"）。
  - 注意：**多数漏洞来源不提供显式否定证据**。因此负例应主要来自"版本比较的明确结论"，而不是"来源没提到"。
- **unknown**：来源未提供该信息。**不得**把 unknown 计入正例或负例，必须单列。

### 6.4 TP / FP / FN 与微平均 / 宏平均

以"系统输出该维度 present"与金标准对照：

| 情形 | 计为 |
| --- | --- |
| 金标准 positive，系统 present | TP |
| 金标准 negative 或 unknown，系统 present | FP |
| 金标准 positive，系统 missing | FN |

- **微平均**：把六个维度的 TP/FP/FN 汇总后统一计算 P/R。
- **宏平均**：先算六个维度各自的 P/R，再取算术平均。
- 两者必须同时报告，且必须附各自的样本量。

### 6.5 哪些能从现有资料获得，哪些必须真实采集

| 类别 | 数量 | 是否需采集 |
| --- | --- | --- |
| `research/cases.json` 已核验案例 | **3 条** | 否（已在仓库） |
| 六个维度的候选标注（需人工核验） | 目标 ≥100 条 | **是** |
| 多跳所需的关系边 | 未知，取决于采集后的事件关系密度 | **是** |

**3 条已核验案例无法支撑 100 条金标准**；其余必须来自真实采集后的人工核验。**不得把采集到的原始数据直接当作金标准**：原始数据只是候选，必须逐条对照来源原文核验后才可标为 `real_verified`。

---

## 7. 缺失依赖、凭据和环境条件

| 项 | 状态（已确认） | 影响 |
| --- | --- | --- |
| `.env` | **不存在**（仅 `.env.example`） | 无任何令牌被配置 |
| `GITHUB_TOKEN` | 未设置 | `ghsa` 会返回 `skipped`（不冒充成功）；该来源是 GitHub 生态 POC 线索的主要出处之一 |
| `DEEPSEEK_API_KEY` | 未设置 | 系统进入 `local_evidence_extraction` 模式；**不影响采集** |
| `OPENALEX_MAILTO` | 未设置 | 仅影响 OpenAlex 的 polite pool，非必需 |
| `INTEL_ALERT_WEBHOOK_URL` / `INTEL_JSON_LOGS` | 未设置 | 告警仅写本地 JSONL |
| playwright + chromium | **均未安装** | 仅影响任务 5 的页面截图；不影响采集与评测 |
| 网络出口 | 本次**未验证**（按要求未发起请求） | 采集能否成功需实测；A 任务文档记载 arXiv 曾返回 HTTP 406、GHSA 因缺令牌未采集 |
| `data/` 目录 | 不存在 | 首次采集会新建；`.gitignore` 已覆盖 |
| `artifacts/tools/syft/syft.exe` | 不存在 | 影响 `tools/run_asset_simulation.py`（资产侧，非采集） |

---

## 8. 采集前需要我确认的事项

1. **数据目录**：使用默认 `data/`，还是设置独立的 `INTEL_DATA_DIR` 以避免与 A 任务每日调度互相干扰？
2. **来源范围**：只跑 12 个推荐来源，还是显式加入 `arxiv`（论文关联维度必需）与 `ghsa`（需令牌）？
3. **是否提供 `GITHUB_TOKEN`**：不提供则 `ghsa` 记 `skipped`，且 POC 维度更可能接近 0。
4. **是否允许下载 arXiv 全文 PDF**：每轮最多 5 篇，会写入快照目录并建立可检索全文块。跨文档与多跳题集需要这类文档。
5. **采集批次**：单次冷启动采集即可，还是需要多天累积？（时效指标依赖多天真实运行，非本任务重点。）
6. **是否同批执行富化与研判**：`close_gaps=True` 或额外调用 `POST /api/enrichment/run`、`POST /api/assessments/run` 会显著增加外网调用与运行时长。
7. **是否需要我先导入演示资产与核验案例**（`POST /api/seed`，非网络操作），以便资产关联维度有素材。
8. **素材归属**：采集所得 `data/` 是否作为 B 任务的临时素材目录，由我整理出金标准草案后再逐条人工核验？

---

## 9. 推荐的后续步骤及验收标准

| 步骤 | 内容 | 验收标准 |
| --- | --- | --- |
| S1 采集（**待批准**） | 12 个推荐来源 + `arxiv`，单次执行，写入独立数据目录 | 存在 `kind=collect` 的运行记录且 `status ∈ {completed, partial}`；逐来源 `fetched/kept/filtered/error/snapshot_hash` 可查；失败来源如实列出，不用空结果冒充成功 |
| S2 素材盘点 | 导出事件清单，统计六维度字段填充率 | 给出事件总数、按来源/类别分布、六维度 present 数/总数；区分 `ai_relevance.included` 与否 |
| S3 富化金标准草案 | AI 辅助初标，所有条目先标 `pending_verification` | ≥100 条候选，全部带 `source_url`；`real_verified` 条目必须有可打开的原文；unknown 单列 |
| S4 问答评测集 | 扩到 50–100 道，覆盖六类 | 六类各有明确分母；每题含 `expected_event_ids` / 证据 / `should_refuse`；语料与分母守卫生效 |
| S5 多跳基线 | 先建 ≥30 道题并测当前系统基线 | 如实记录失败样本；**不得**把预存关系的格式化输出记为"已实现多跳" |
| S6 策略感知建议 | 待 S2–S3 完成后评估 schema 变更 | 变更前先提交受影响模块、字段定义、兼容与迁移风险，并与 A 任务负责人协调 |

### 已知风险

| 风险 | 说明 |
| --- | --- |
| POC 维度结构性为 0 | 采集器中没有专门的 POC 来源；该项可能无法达到有效样本量 |
| 多跳关系数据稀疏 | 现有实现只展示事件内预存 `relationships`，没有独立关系数据集；30 道多跳题需要先验证关系密度 |
| JSON 类型来源不入 RAG | 跨文档题只能建立在 HTML/XML/PDF 类来源上（如 OWASP、NIST、EU AI Act、安全博客、arXiv 全文） |
| 冷启动窗口偏大 | 首次采集会一次性纳入窗口内历史条目，时效分布偏低（A 任务已观察到 `≤24h` 比例很低） |
| 共享 `INTEL_DATA_DIR` 冲突 | 与 A 任务每日调度共用目录会互相推进 `cursor` |
| 标注工作量 | ≥100 条富化标注 + 50–100 道问答 + ≥30 道多跳题，人工核验是主要成本，AI 只能辅助初标 |

---

## 附录 · 本报告未做的事

- 未发起任何外部网络请求，未运行任何采集命令或定时任务
- 未修改数据库，未创建或修改 `data/` 目录
- 未安装任何依赖
- 未修改任何既有代码或配置文件；`docs/B_DATA_READINESS.md` 是本阶段唯一新增文件
- 未执行任何 git 写操作（无 add / commit / push / merge / rebase / 分支切换）
- 未读取、未输出任何密钥或令牌值

---

# 更新（2026-09-30）：全文采集与评测准备的实际结果

本节记录本报告写完之后、已**实际执行**的进展，用于替代上文第 4/5/6 节的"待采集"判断。

## 更新 1 · 数据现状（实测）

| 指标 | 本报告初稿 | 现在 |
| --- | ---: | ---: |
| 事件总数 | 93 | 93 |
| RAG 文档 | 1 | **22** |
| RAG 分块 | 849 | **3639** |
| 快照总数 | 29 | **42** |
| arXiv 全文入库论文 | 0 | **16** |
| 数据库大小 | 4,272,128 B | **8,183,808 B** |

数据目录仍为 `D:\ICT\intel-data-b`；写入前备份位于
`D:\ICT\intel-data-b-backups\intel-before-phaseB-20260930-094325.sqlite`。

## 更新 2 · 四个原始目标的最新完成度

| 目标 | 状态 | 依据 |
| --- | --- | --- |
| ≥100 条**经人工核验**的富化关系 + TP/FP/FN | **未完成** | 候选素材已足够（见下），但**一条都还没有人工核验**，未统计 TP/FP/FN |
| ≥30 道带真实推理路径的多跳题 | **未完成，且被阻塞** | 语料已增至 22 个文档，但**没有任何实体/关系抽取能力**，关系仍只有 KEV 的 `known_exploited` 一种谓词 |
| 50–100 题固定问答集 + 准确率/召回率/引用/拒答/P50/P95 | **未完成** | 只做了 13 条冒烟测试；且发现共享模块缺陷 D-1（52% 语料被丢弃），修复前评测不可信 |
| 资产策略字段（维护窗口/业务重要性/禁止动作/负责人/可接受停机） | **未实现** | `assets` 表 0 条，字段在 schema 中不存在，需改共享 schema |

### 富化候素材的当前规模（粗算上界，非金标准）

| 维度 | 可形成的候选关系数 |
| --- | ---: |
| 论文关联 | 41 个事件带 `paper` |
| 版本范围 | 50 条 `affected` |
| 修复版本 | 12 条带 `fixed_version` |
| CVSS | 22 条 |
| 证据关系 | 26 条 |
| POC | **0**（无专门采集器，结构性为 0） |

候选池合计约 151 条，**算术上足以支撑 100 条**，但必须逐条对照来源原文人工核验后才能标记
`real_verified`；**本阶段未做任何人工核验**。

## 更新 3 · 新增的阻塞项（需你决策）

| # | 阻塞项 | 所属模块 | 为什么需要你批准 |
| --- | --- | --- | --- |
| D-1 | `app/rag.py::chunks_from_records` 先 `.strip()` 再校验长度，静默丢弃 **1906/3639（52.4%）** 分块 | 共享问答链路 | 修复需要改 `app/rag.py` 或 `app/rag_corpus.py`，属主问答链路 |
| D-2 | `app/rag.py::retrieve_chunks` 的 `len(matched) < 2` 守卫使"英文专名 + 中文疑问句"得 0 命中 | 共享问答链路 | 同上 |
| D-3 | 问答层 `max_chunks=6` 导致 `distinct_docs` 恒 ≤1，**不具备跨文档综合能力** | 共享问答链路 | 同上（能力补齐属新开发） |
| T2 | 无实体/关系抽取，多跳无法构建 | 需要新能力 + 可能改 schema | 涉及共享 schema，需与 A 任务协调 |

**在 D-1 修复前，基于问答链路的准确率指标不可信**，因此本阶段没有、也不应发布任何准确率数字。

### 更新 3.1 · 修复状态（2026-09-30，保留上表原始结论）

| # | 原阻塞项 | 现状 | 证据 |
| --- | --- | --- | --- |
| D-1 | 分块被静默丢弃 | **已修复** | 可见分块 1733 → **3639/3639（100%）**；`app/rag.py::chunks_from_records` 改用存储原文校验并保留原文；新增 29 项回归测试 |
| D-2 | 单英文专名 + 中文问句 0 命中 | **已修复** | `DistillGuard 是做什么的？` 0 → **12** 命中；阈值改为"文档频率 ≤ 语料量/20"；新增 18 项测试 |
| D-4 | 拒答文案与文档引用并存 | **已修复** | 矛盾用例 2 → **0**；`app/intelligence.py::with_rag` 在事件路径无证据、文档路径有证据时以文档为准；新增 8 项测试；公开返回字段未变 |
| D-3 | 不具备跨文档综合能力 | **已重新评估，仍未实现** | 引用层已能返回 2 个不同文档（修复前恒 ≤1），但答案仍是原文摘录拼接；瓶颈定位在**答案生成阶段**（`answer_with_rag(generator=None)`）。需单独授权 |
| T2 | 无实体/关系抽取，多跳无法构建 | **未变** | 仍需新能力 + 可能改共享 schema |

**修复后仍存在的两个检索边界（未修，需单独授权）**：

1. `app/rag.py::terms()` 的中英扩展表仅 7 条，纯中文问句（如"欧盟法案对透明度的要求"）仍 0 命中。
2. RAG 路径只用问题原文检索，不继承会话上下文，多轮追问（"它的…"）仍 0 命中。

测试：B 任务 6 个测试文件合计 **95 passed**；全量 **373 passed**（318 基线 + 55 新增）。
真实数据库在本轮**零写入**（大小与 SHA-256 未变）。

## 更新 4 · 本阶段新增/修改的文件

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `tools/run_paper_fulltext.py` | 新增（本任务） | 受限流保护的 arXiv 全文入库工具；本阶段增加重定向链可观测性 |
| `tests/test_paper_fulltext_tool.py` | 新增测试 | 8 项离线测试（限额 / 429 / 重定向 / 跳过 / 白名单 / 解析失败安全） |
| `tests/test_rag_retrieval_b_task.py` | 新增测试 | 30 项检索回归测试（19 条用例 + 跨文档断言 + 专项） |
| `docs/B_PAPER_FULLTEXT_REPORT.md` | 新增文档 | 全文采集与数据完整性 |
| `docs/B_RAG_RETRIEVAL_EVAL.md` | 新增文档 | 语料清单、检索用例、跨文档分布 |
| `docs/B_QA_SMOKE_EVAL.md` | 新增文档 | 13 条冒烟测试与引用核验 |

**未修改**：`app/agents.py`、`app/collectors/`、`app/reliability.py`、`app/scheduled_job.py`、
`app/self_healing.py`、`app/multi_agent_runtime.py`、`scripts/`、`.github/`、`reports/`、
`app/rag.py`、`app/rag_corpus.py`、数据库 schema。

## 更新 5 · 本节未做的事

- 未修改任何共享模块或 schema（D-1/D-2/D-3/T2 均只报告、未修）
- 未做任何人工核验，未发布任何准确率/召回率数字
- 未处理剩余 21 篇非 arXiv 论文
- 未安装任何依赖（`fontTools` 缺失仅报告）
- 未执行 Git 写操作
