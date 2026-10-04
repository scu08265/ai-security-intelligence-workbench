# B 任务重评测（2026-10-02 批次）阶段报告

本轮原因：**RAG 回答链路已在 `8db19cf` 修改**（`app/rag.py` +151/−4、新增
`app/b_evaluation.py`、`app/storage.py` 增加 POC 合并入口）。旧的人工金标准
（`qa_human_score.json`，2026-09-30 冻结）描述的是改造前的回答，**不能套用到
新回答上**，因此本轮重跑评测并重新组织人工核验材料。

## 0. 基线与环境

| 项 | 值 |
|---|---|
| 仓库 | `D:\ICT\ai-security-intelligence-workbench-git` |
| 分支 | `feat/b-reevaluation-20261002`（自 `8db19cf` 开） |
| 数据目录（独立、只读） | `D:\ICT\intel-data-b` |
| 数据库 | `intel.sqlite`，8,183,808 B，SHA256 `4095A5B1…254285`（全程未变） |
| Python / Node | `.venv` Python 3.13.7 / node v24.19.0 |
| 模型 API | 未配置（`DEEPSEEK_API_KEY` 不存在）→ 回答走本地抽取，评测不依赖外网 |

## 1. 机器评测（P0，已完成）

命令（真实执行）：

```
.\.venv\Scripts\python.exe tools\run_b_qa_eval.py ^
    --out artifacts\b_eval\formal_qa_results_20261002.json
.\.venv\Scripts\python.exe tools\build_b_qa_performance_report.py ^
    --run A_prev=artifacts\b_eval\formal_qa_results.json ^
    --run B_prev=artifacts\b_eval\formal_qa_performance_run2.json ^
    --run C_20261002=artifacts\b_eval\formal_qa_results_20261002.json ^
    --out artifacts\b_eval\qa_performance_20261002.json
```

结果（50 题，真实库只读 + 临时副本，串行，无网络问答服务）：

| 指标 | 值 | 分母口径 |
|---|---|---|
| 文档命中率 | 32/36 = 88.89% | 带预期 `document_key` 的题 |
| 预期词命中率 | 31/38 = 81.58% | 带预期要点词的题；机械字符串判定，非语义准确率 |
| 拒答一致率 | 42/50 = 84.00% | 全部 50 题 |
| 引用可追溯率 | 217/217 = 100.00% | 全部引用（引用 ID 可在库中取回） |
| P50 / P95 | 442.8 ms / 591.0 ms | 50 样本，单题端到端（含本地检索） |
| 超时 / 异常 | 0 / 0 | 超时阈值 5000 ms |

新旧批次对照（**批次独立计算，不合并分位数**）：

| 批次 | 作答 | 拒答 | P50 | P95 | 异常 | 超时 |
|---|---|---|---|---|---|---|
| A_prev（改造前） | 39 | 11 | 427.1 | 584.6 | 0 | 0 |
| B_prev（改造前） | 39 | 11 | 427.4 | 566.5 | 0 | 0 |
| **C_20261002（本轮）** | **46** | **4** | **442.8** | **591.0** | 0 | 0 |

行为发生翻转（旧拒答 → 新作答）的 7 题：`BQA-025、026、028、029、030、048、049`。
另有 31 题的答案文本与旧批次不同；16 题的答案正文与引用与旧批次逐字一致
（`BQA-008、013、018、022、024、027、033、035、036、037、041、042、043、045、046、050`）。

## 2. 人工核验材料（P0，已备齐，等待人工判定）

新增工作表（人工列全部留空，机器建议单独存放）：
`artifacts/b_eval/qa_final_confirmation_worksheet_20261002.csv`。

配套材料：

| 文件 | 用途 |
|---|---|
| `artifacts/b_eval/qa_reeval_20261002_review_packet.md` | **覆盖全部 50 题**的复核清单（16 题逐字未变 / 30 题有变化 / 11 题争议或拒答翻转），由 `tools/build_b_qa_reeval_review_packet.py` 生成 |
| `artifacts/b_eval/qa_reeval_20261002_recommended_labels_proposal.csv` | 逐题**建议标签提案**（B 类机器辅助建议，非人工金标准），50 行全部通过标签合法性校验 |
| `artifacts/b_eval/qa_reeval_20261002_review_packet.md` 第一节 | 16 道答案与引用逐字一致的题，可批量确认是否沿用旧标签 |

工作表修正：原确认表缺少评分工具判定"应拒答题分母"所需的 `should_refuse` 列
（旧表有），会导致拒答 recall 变 `None`、precision 变 0。已在
`tools/build_b_qa_candidate_answers.py` 补上该列并重新生成工作表（人工列仍为空）。

人工确认已完成 **50/50**：用户对覆盖 50 题的复核清单整体确认（"全部采用"），
标签通过 `tools/apply_b_qa_labels.py` 回填，署名 `人工复核-用户确认`、
日期 `2026-10-04`；三列人工判定与署名在
`artifacts/b_eval/qa_final_confirmation_worksheet_20261002.csv` 内，缺署名 0 行。

人工指标（`artifacts/b_eval/qa_human_score_20261002.json`，`human_judged_cases=50`）：

| 指标 | 新批次（改造后） | 旧基线（改造前，2026-09-30） |
|---|---|---|
| 答案准确率 | 5/38 = 13.16% | 7/33 = 21.21% |
| 答案准确率（严格口径 correct/incorrect） | 5/12 = 41.67% | 7/9 = 77.78% |
| 引用支持率 | 3/36 = 8.33% | 1/31 = 3.23% |
| 拒答准确率 | 4/12 = 33.33%（judged 12） | 6/17 = 35.29%（judged 17） |
| 拒答召回率 | 4/12 = 33.33% | 6/12 = 50.00% |
| 拒答精确率 | 4/4 = 100.00%（0 误拒） | 6/11 = 54.55% |
| P50 / P95 | 442.8 / 591.0 ms | 427.1 / 584.6 ms |

口径说明：`partial`、`unknown` 不计为正确；空值不进答案/引用分母；应作答且作答的题
拒答维度记 `not_applicable`（因此新批次拒答分母是 12 而不是 50）。
旧 `qa_human_score.json` 未被覆盖（仍是 21.21% / 3.23% / 50%）。

## 3. 关系候选与 POC 维度（P0，已补齐；资产维度仍缺真实数据）

命令（真实执行，只读）：

```
set INTEL_DATA_DIR=D:\ICT\intel-data-b
.\.venv\Scripts\python.exe tools\build_b_relation_candidates.py ^
    --out evaluation\b_relation_candidates_20261002.json
```

### 3.1 为什么原来 POC 为 0（三项实测证据）

1. 本机 `intel.sqlite` 93 条事件中 **`poc[]` 非空 0 条**，且 `references[]` 已被
   拍平成字符串、不带 `tags`，无法从库内推导；
2. 本机仅有的两份 NVD 快照（B 数据目录 2 个文件 / 另一份 6 个文件）与本库
   37 条 CVE 事件的交集只有 1–2 条，且**都不带 Exploit 标签**——快照与库不同源；
3. 在临时副本上真实运行回填工具：

```
.\.venv\Scripts\python.exe tools\backfill_nvd_poc.py --report artifacts\b_eval\nvd_poc_backfill_20261002.json
{"snapshot_files": 2, "events_with_poc": 144, "events_updated": 0,
 "events_unchanged_or_missing": 144, "snapshot_errors": 0}
```

即：用既有快照回填是 **0 条**。队长报告里的 16 条 Exploit 引用不在本机任何一份库中
（另一份 `…-main\…\data\intel.sqlite` 同样是 0 条）。

### 3.2 解决办法：按库内 CVE 定向拉取 NVD（已执行）

依据 `docs/DATA_SOURCE_DECISIONS.md`（权威来源 = NVD `references[].tags` 含 `Exploit`），
对本库 37 个 CVE 逐个调用 NVD 官方接口，把原始响应存进**库副本**的 snapshots 目录，
再跑既有回填工具：

```powershell
# 37 次 GET https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=<CVE-ID>
# 写入 D:\ICT\intel-data-b-poc-20261002\snapshots\nvd\CVE-*.json（无 BOM）
$env:INTEL_DATA_DIR='D:\ICT\intel-data-b-poc-20261002'
.\.venv\Scripts\python.exe tools\backfill_nvd_poc.py `
    --report artifacts\b_eval\nvd_poc_backfill_cve_scope_20261002.json
.\.venv\Scripts\python.exe tools\build_b_relation_candidates.py `
    --out evaluation\b_relation_candidates_20261002_poc.json
```

真实输出：

```
拉取：ok=37 fail=0
回填：{"snapshot_files": 39, "events_with_poc": 160, "events_updated": 16,
       "events_unchanged_or_missing": 144, "snapshot_errors": 0}
候选：153 条 {'paper_link': 37, 'version_range': 50, 'fixed_version': 12,
             'cvss': 22, 'poc': 32, 'asset_assessment': 0}
```

**`events_updated = 16` 与队长说的"已回填 16 条 NVD Exploit 引用"完全一致**，
说明这条路径就是队长数据的来源。POC 维度从 **0 条候选变成 32 条可评测候选**，
覆盖 16 个事件、32 条公开利用参考（每条含 URL、`status=public_exploit_reference`、
`source_id=nvd:*` 与 `tags`）。

数据可追溯：快照清单（CVE、文件 SHA256、公开引用数、Exploit 标签数）
写在 `artifacts/b_eval/nvd_poc_snapshot_manifest_20261002.json`；
**原库未被修改**（SHA256 仍为 `4095A5B1…254285`），副本路径
`D:\ICT\intel-data-b-poc-20261002`，与原库唯一差异是 `event.poc[]` 新增。

### 3.4 资产维度（按队长口径：无真实资产时明确标为合成数据）

本机没有授权真实资产清单，因此按队长口径**使用明确标注的合成资产**补该维度，
并且**每条候选都带 `asset_is_demo=true` / `synthetic=true`**，不冒充企业资产：

```
导入：config/assets.example.json（synthetic=true, is_demo=true）+ 对应策略
      6 个合成资产 · 批次 cdx-2327e1e35feaecbe91c9 · policy_asset_count=6
研判：33 条事件↔资产记录（affected 13 / not_affected 18 / needs_confirmation 2）
候选：asset_assessment 33 条，全部标 synthetic=true
```

六维度覆盖：`paper_link 37 / version_range 50 / fixed_version 12 / cvss 22 /
poc 32 / asset_assessment 33`，共 **186 条候选，覆盖缺口为空**。

另有一条真实侧证据：把工作台自身 7 个真实运行时组件导入同一副本
（`is_demo=false`），与库内漏洞组件零交集 → 0 关联
（`artifacts/b_eval/asset_inventory_probe_20261002.json`）。也就是说：
**真实资产路径已验证可用，但本机没有能产生真实关联的业务资产清单**。

证据：`artifacts/b_eval/asset_dimension_synthetic_20261002.json`
（批次、6 个合成资产、状态计数、原库/副本 SHA256）、
`evaluation/b_relation_candidates_20261002_full.json`。

待人工/待决定：这 32 条 POC 候选的复核表尚未生成（可按现有
`relation_annotation_worksheet_v2.csv` 的列结构生成供你批量签核）；
若团队认可"NVD 打标签即权威证据"，也可直接按 `public_exploit_reference` 口径记为
机器可核验、不加人工标签。两者都不影响上面的候选数量。

### 3.3 POC 证据强度细分（已生成轻量签核表）

命令：

```powershell
.\.venv\Scripts\python.exe tools\build_b_poc_review_worksheet.py
```

真实输出：

```
POC 候选: 32 条 | 事件: 16 个
URL 类型: {"公开利用库": 15, "厂商/研究博客": 8, "安全公告": 5,
           "issue/PR": 1, "代码仓库/其他": 1, "利用脚本文件": 1, "缺陷跟踪": 1}
机器建议（是否可利用证据）: {"yes": 16, "no": 16}
```

要点：

* 系统口径不变（`public_exploit_reference`，不代表执行或复现过）；
  签核表只额外回答"这条算不算可利用证据"。
* **32 条候选里只有 16 条是公开利用库/PoC 仓库/脚本文件，且只覆盖 16 个 POC 事件中的 5 个**；
  其余 16 条是安全公告、厂商分析博客或缺陷跟踪页——写成"32 个漏洞都有 PoC"会口径膨胀。
* 人工签核列（`人工判定_是否可利用证据`、`人工核验人`、`人工核验时间`）保持空白，
  由人工填写；机器建议列只是建议。
* 全程不下载、不执行任何利用代码。

产物：`artifacts/b_eval/relation_poc_review_20261002.csv`（32 行签核表）、
`artifacts/b_eval/relation_poc_classification_20261002.json`（分类结果）。

人工签核已完成（用户确认"按建议采纳"，署名 `人工复核-用户确认`、日期 `2026-10-04`，
输入留档 `artifacts/b_eval/relation_poc_review_20261002_user_confirmed.csv`）：

```
人工判定：yes 16 / no 16（32 条 / 16 个事件）
有人工认定可利用证据的事件：5 / 16（CVE-2014-4114、CVE-2014-6332、
                                        CVE-2021-27876、CVE-2021-27877、CVE-2021-27878）
仅公告/博客的事件：11
```

**一处已知分歧（如实记录，未擅自改动人工标签）**：分类规则原先只看 URL 第一段路径，
把专用 PoC 仓库 `github.com/lntrx/CVE-2021-28663` 误判为"代码仓库/其他"（建议 no）。
修正为"任意路径段含 CVE 即视为专用 PoC 仓库"后，该行机器建议变为 yes
（机器建议分布 17/15）。人工标签仍为已签核的 `no`，是否上修由人工决定；
差异记在 `relation_poc_classification_20261002.json →
machine_suggestion_changes_after_rule_fix`。

## 4. 跨文档 / 多跳真实关系边（P1，语料不具备条件）

两轮真实探测（只读语料）：

1. **论文互引**：22 篇文档中 16 篇是 arXiv 论文；正文出现的 184 个 arXiv 标识
   与语料内文档**交集 0** → 没有"论文 A 引用论文 B"这类可核验边。
2. **论文 ↔ 漏洞事件**：论文正文提到的 CVE 与库内 37 个 CVE 事件**交集 0**。
3. 补充探测：按标题特征词跨文档匹配，命中的是 `Agents`、`Adversarial`、
   `Effectiveness` 这类通用词，属于字符串共现，**按规则不得写成推理关系**。

### 4.1 第一批真实关系边（已补 1 条，可核验）

对 22 篇文档做全文互查后，语料内**只存在 1 条**真实的文档间引用：

```json
{"subject": "paper:2609.30266", "predicate": "cites", "object": "paper:2609.30217",
 "evidence": {"chunk_id": "chunk-5d0b41d50273664bec30cd2c",
              "char_start": 558, "char_end": 600,
              "quote": "Instrumental monitor evasion emerges under"},
 "verified": true}
```

来源是 `paper:2609.30266` 参考文献里的 `[20] David Schmotz, ... Instrumental monitor
evasion emerges under ordinary task pressure. Preprint, 2026.`；偏移已回读校验
（`text[558:600]` 等于 quote）。登记在
`evaluation/b_cross_document_edges_20261002.json`，
路径检索器新增 `--edges` 只加载 `verified=true` 且带 `chunk_id` 的边。

### 4.2 为什么原来跨文档计数是 0/21（精确诊断）

带这条边重跑（`artifacts/b_eval/multihop_path_validation_20261002.json`）：

```
图规模: 节点 160 / 边 122 / 边类型 ['cites', 'component_is', 'mentioned_in']
候选题: 31 | 找到路径: 10 | 不连通: 21
按类型: {"two_hop": {"total": 10, "path_found": 10},
         "cross_document": {"total": 21, "no_path": 21}}
缺失边类型: term_node_with_evidence ×21、document_to_document ×126
21 道跨文档题的失败原因：**全部是"起始术语不在图中"**
（例：BMH-011 起始 'AUROC' 不是图节点，目标是 doc:paper:2609.28915）
```

两个独立缺口：

1. **术语节点缺失**：图里没有 `term:*` 节点，21 道题的起点（AUROC、prompt injection…）
   全部解析失败——这是**图构建缺口**，不是数据缺失（术语确实在语料里有带偏移的证据）；
2. **文档间边缺失**：即使补上术语节点，声明的 文档A→文档B 链路仍缺 126 条文档间边；
   本轮只找到 1 条真实引用边，且它连接的两篇文档都不是这 21 题的目标文档。

因此**不把 0/21 改写成 ≥1**：那需要补新来源（互相引用的论文、讨论具体论文或 CVE
的安全博客），或由任务负责人同意把该指标口径改成"术语可达性"（1 跳检索，不是推理）。
两条路都需要队长决定，本轮不擅自换口径、不造边。

### 4.3 按队长决定（选项 A：补来源）后的结果：跨文档 10/21

流程（`tools/build_b_cross_document_edges.py`，`--stage fetch/screen/ingest/edges`）：

1. arXiv 检索 5 组主题 → 49 篇候选 → 下载 PDF（限速 3s/请求）；
2. 用项目自带 PDF 解析器抽文本筛选 → **13 篇命中目标文档**；
3. 取命中目标文档且术语覆盖最好的 **8 篇**入库到**库副本**
   （`paper_fulltext.ingest_arxiv_paper`，`document_key=paper:<arxiv id>`）；
4. 在入库后的 chunk 里定位引用串与术语，**只认标题/官方编号级匹配**，
   记录 `chunk_id + char_start + char_end + quote`，并做
   `text[char_start:char_end] == quote` 回读校验。

产出：

| 项 | 结果 |
|---|---|
| 新增文档 | **8 篇**（见 `artifacts/b_eval/new_documents_20261002.json`，含 PDF sha256 与快照哈希） |
| 文档间边（`cites`） | **12 条**，如 `paper:2609.24016 --cites--> official:eu_ai_act`，引用串为 `Regulation (EU) 2024/1689` |
| 术语第一跳（`mentioned_in`） | **85 条**（覆盖 21 个起始术语中的 20 个） |
| 独立回读校验 | **97/97 通过**（另写脚本从库里重读 chunk 逐条核对） |
| 跨文档路径 | **10/21 连通**（原 0/21），two_hop 仍 10/10 |
| 术语可达性（独立诊断） | **29/31 可达**，2 个不可达（`kernel-level`、`Qwen3`） |
| 未连通 | **11 题保留 `no_path`** + 失败原因，未隐藏 |

连通样例（节点 / 边 / 证据 ID 全部可列）：

```
BMH-014: term:reinforcement learning →(mentioned_in) paper:2609.22882 →(cites) official:eu_ai_act
         evidence: chunk-e1ef2bd6c0ae27c4de3d048c, chunk-270a4e17aeac622b6b337ae5
BMH-021: term:jailbreak →(mentioned_in) paper:2609.03999 →(cites) source:owasp_genai
         evidence: chunk-64fda3d9789903475a50de40, chunk-21edb1ae9ef322ae90f6adf2
```

仍未连通的 11 题及原因（均在输出里保留）：

| 题号 | 目标文档 | 原因 |
|---|---|---|
| BMH-011/012/013/023/029/031 | `paper:2609.28915` | 新增论文里没有引用该论文的（需找"引用它的"来源） |
| BMH-018/024 | `paper:2606.15617` | 同上 |
| BMH-015 | `source:security_blog` | 博客文档不被学术论文引用 |
| BMH-022/028 | `official:eu_ai_act` | 该术语的第一跳落在只引用 OWASP 的论文上，未形成到 EU AI Act 的路径 |

口径说明：连通路径的**终点**与候选题声明的目标一致，但中间节点可能与声明链路不同，
`matches_declared_path` 如实输出，不假装完全一致；**术语可达性单列为诊断字段**，
不参与 `path_found` 判定；语料由 22 篇增至 30 篇，**50 题 QA 基线不动**。

复核材料：`artifacts/b_eval/cross_document_paths_20261002.md`
（8 篇新来源清单 + 10 条连通路径的节点/边/evidence/可回读 quote/上下文 + 11 条未连通原因）。
该文件由 `tools/build_b_cross_document_edges.py --stage packet` 生成；
证据按"边"精确对应（同一 chunk 承载多条边时不会串位）。

**本轮未能补上的部分（如实记录）**：为了打通剩余 8 题（目标为
`paper:2609.28915`、`paper:2606.15617`），需要"引用这两篇论文的来源"，本轮尝试：

1. arXiv 定向检索 4 组主题（25 篇候选）→ 全文扫描 → **未发现引用这两篇的论文**
   （检索只召回这两篇论文自身）；
2. OpenAlex 与 Semantic Scholar 反查被引 → 本环境 **HTTP 429 限流**，未能取得结果。

因此剩余 8 题保持 `no_path`，原因写在复核材料第三节。要打通需换网络环境重试被引反查，
或补充"引用这两篇论文"的具体来源。

## 5. 赛题指标页面与权威 JSON 一致性（P1，已完成）

命令与结果（只读，27 个字段）：

```
.\.venv\Scripts\python.exe tools\check_b_scorecard_consistency.py ^
    --out artifacts\b_eval\scorecard_consistency_20261002.json
对照字段数: 27 | 不一致: 0
页面是否显示新批次: False
```

- 页面口径（`app/b_evaluation.py` → `/api/competition/scorecard` → 前端卡片）
  与冻结文件逐字段一致：`qa_human_score.json`、`qa_performance_stats.json`、
  `relation_score_all.json`、`multihop_path_validation.json`、`b_demo_screenshots.json`。
- 页面显示的 `21.21% / 3.23% / 50%` 等**确实来自改造前的冻结人工基线**，
  页面上已有横幅"这是改造前的冻结人工基线；partial、unknown 不按正确回填，
  代码修改后需重新人工核验"。
- **20261002 新批次不会自动出现在页面上**（页面只读固定文件名）。是否让页面
  引用新批次属于 `app/` 共享代码，本轮未改。

## 6. 测试与回归（真实执行）

```
node --check app\static\app.js
→ exit=0（无输出）

.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -rsx
→ 1 failed, 576 passed, 1 warning in 130.27s
```

**基线红点如实记录**：失败用例
`tests/test_rag_mixed_language_query.py::test_mid_frequency_technical_terms_can_carry_a_query
[multi-agent …]`。对照实验：`6daea3a`（改造前）30 passed；`8db19cf`（分支点）
1 failed；`7dcb064`（当前 main）1 failed。即该回归由 `8db19cf` 的 RAG 加固引入，
**在 main 上同样存在**，不是本轮改动造成。涉及共享问答主链路，本轮不改，已上报。

新增回归测试 `tests/test_b_reeval_20261002.py`（9 条，全绿）覆盖：新批次 50 题、
旧文件保留、批次不混算、C 类人工=0、空工作表不出指标（不写 0%）、空答案维度
不进分母、拒答计数自洽、页面与 JSON 一致且不显示新批次。

## 7. 工具改动（仅 B 自己的评测工具，默认行为不变）

| 文件 | 改动 |
|---|---|
| `tools/auto_review_qa.py` | 新增 `--results`（默认为原路径） |
| `tools/classify_b_refusals.py` | 新增 `--results`、`--auto-review`；**修正计数 bug** |
| `tools/build_b_qa_candidate_answers.py` | 新增 `--results`/`--auto-review`/`--refusal-classification`/`--gold-worksheet`/`--suffix` |
| `tools/score_b_qa_annotations.py` | 新增 `--auto-review`/`--results`/`--machine-adjudication` |
| `tools/check_b_scorecard_consistency.py` | 新增（只读核对页面与权威 JSON） |

计数 bug 说明：旧 `refusal_failure_classification.json` 里
`correctly_refused` 统计的是**未拒答**的题数，与 `wrongly_answered` 重复计数。
旧文件按历史基线保留原样；新批次修正后为 **正确拒答 4 / 错误作答 8**。
用默认参数重算旧工作表，结果仍是答案 7/33 = 21.21%、引用 1/31 = 3.23%、
拒答准确 35.29%、召回 50%、精确 54.55%，与 `qa_human_score.json` 一致 → 改动不影响旧基线。

## 8. 仍未完成 / 需要人工

1. **50 题人工重核验**（P0，必须由人完成）：机器建议**不得**当作人工标签。
2. **POC 维度**：需要队长提供已回填的库或对应 NVD 快照，否则保持 0 并标注前置缺失。
3. **跨文档 0/21**：需要新来源才能产生真实关系边。
4. **页面展示新批次**：属于 `app/` 共享代码，需队长决定是否改。

## 9. 复现命令汇总

```powershell
cd D:\ICT\ai-security-intelligence-workbench-git
$env:INTEL_DATA_DIR='D:\ICT\intel-data-b'
.\.venv\Scripts\python.exe tools\run_b_qa_eval.py --out artifacts\b_eval\formal_qa_results_20261002.json
.\.venv\Scripts\python.exe tools\build_b_qa_performance_report.py --run A_prev=artifacts\b_eval\formal_qa_results.json --run B_prev=artifacts\b_eval\formal_qa_performance_run2.json --run C_20261002=artifacts\b_eval\formal_qa_results_20261002.json --out artifacts\b_eval\qa_performance_20261002.json
.\.venv\Scripts\python.exe tools\auto_review_qa.py --results artifacts\b_eval\formal_qa_results_20261002.json --out artifacts\b_eval\qa_auto_review_20261002.json
.\.venv\Scripts\python.exe tools\classify_b_refusals.py --results artifacts\b_eval\formal_qa_results_20261002.json --auto-review artifacts\b_eval\qa_auto_review_20261002.json --out artifacts\b_eval\refusal_failure_classification_20261002.json
.\.venv\Scripts\python.exe tools\build_b_qa_candidate_answers.py --suffix _20261002 --results artifacts\b_eval\formal_qa_results_20261002.json --auto-review artifacts\b_eval\qa_auto_review_20261002.json --refusal-classification artifacts\b_eval\refusal_failure_classification_20261002.json
.\.venv\Scripts\python.exe tools\build_b_relation_candidates.py --out evaluation\b_relation_candidates_20261002.json
.\.venv\Scripts\python.exe tools\check_b_scorecard_consistency.py --out artifacts\b_eval\scorecard_consistency_20261002.json
.\.venv\Scripts\python.exe -m pytest tests\test_b_reeval_20261002.py -q -p no:cacheprovider -rsx
```
