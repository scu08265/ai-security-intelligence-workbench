# B 任务 · 演示证据报告

| 项 | 值 |
| --- | --- |
| 日期 | 2026-09-30 |
| 运行器 | `tools/run_b_demo_evidence.py` |
| 结果文件 | `artifacts/b_eval/demo_evidence.json` |
| 环境 | Python 3.13.7 / Windows / 本地关键词检索 / 未配置模型（`local_evidence_extraction`） |
| 数据目录 | 临时副本（真实库只读，SHA-256 未变） |

## 1. 五个场景的真实运行结果

| 场景 | 问题 | run_id | 引用数 | 拒答 | 耗时 | 状态 |
| --- | --- | --- | ---: | --- | ---: | --- |
| DEMO-01 基础事实问答 | DistillGuard 这篇论文的标题是什么？ | `run-124ed9b12439` | 5 | 否 | 458 ms | ok |
| DEMO-02 多轮追问 | 它检测什么？（上一轮为 DistillGuard） | `run-9f802e61ccbe` | **0** | **是** | 362 ms | **partial（如实记录）** |
| DEMO-03 跨文档问答 | AUROC 在哪些文档中被讨论？ | `run-44937f5490a7` | 5 | 否 | 419 ms | ok |
| DEMO-04 证据不足拒答 | 明天的天气怎么样？ | `run-d388cbcb0c92` | 0 | **是** | 397 ms | ok（正确拒答） |
| DEMO-05 引用定位与导出 | 什么是提示词注入？ | `run-89a8e774a919` | 6 | 否 | 427 ms | ok |

每条记录都包含：真实 `run_id`、`asked_at`、问题、答案前 600 字、**每个引用的
`chunk_id` / `document_id` / 字符区间**、耗时、模式。

## 2. 诚实声明

| # | 事项 |
| --- | --- |
| 1 | **截图已补拍（2026-09-30）**：原 `environment.screenshot = "not_captured"` 记录的是首次运行环境。本轮改用**已安装的 Microsoft Edge headless**（`tools/render_b_demo_screenshots.py`）补拍 6 张：应用工作台首页 1 张 + 5 个场景的**证据渲染页**各 1 张。截图内容全部来自真实运行结果，未伪造 run_id/引用/耗时；渲染页性质已在图中标注。|
| 2 | **DEMO-02 是部分失败**：多轮追问在 RAG 路径不继承会话上下文，得到 0 引用并拒答。这是真实结果，未包装成成功。 |
| 3 | **DEMO-03 不是多跳推理**：它只验证检索层能返回多篇文档的引用；系统没有跨文档综合能力。 |
| 4 | 运行 ID 与耗时来自实际执行，未编造。 |

## 3. 引用可核验性

5 个场景共产生 16 条文档引用，`citation_ids_retrievable` 全部等于引用数，
即**每条引用的 `chunk_id` 都能在库中取回**，并带有字符区间，可定位到原文。

## 3.1 截图清单（2026-09-30 补拍）

| 文件 | 内容 | 对应 run_id |
| --- | --- | --- |
| `docs/screenshots/b-qa-00-workbench.png` | 应用工作台首页（真实 UI，数据目录为临时副本） | — |
| `docs/screenshots/b-qa-01-basic.png` | DEMO-01 基础事实问答（5 条引用，可追溯 5/5） | `run-124ed9b12439` |
| `docs/screenshots/b-qa-02-multiturn.png` | DEMO-02 多轮追问（拒答、0 引用，如实记录失败） | `run-9f802e61ccbe` |
| `docs/screenshots/b-qa-03-crossdoc.png` | DEMO-03 跨文档问答（5 条引用，覆盖 2 个文档） | `run-44937f5490a7` |
| `docs/screenshots/b-qa-04-refusal.png` | DEMO-04 证据不足拒答 | `run-d388cbcb0c92` |
| `docs/screenshots/b-qa-05-citation.png` | DEMO-05 引用定位与导出（6 条引用） | `run-89a8e774a919` |

机器可读清单：`artifacts/b_eval/b_demo_screenshots.json`（含每张图的 run_id、问题、引用列表、耗时、文件路径）。

**截图性质说明（不可省略）**：`b-qa-00` 是真实应用 UI 页面截图；`b-qa-01`～`b-qa-05` 是把
**真实运行结果**（`demo_evidence.json`）渲染成证据页后的截图，**不是浏览器内逐字交互的会话录屏**。
之所以如此：本项目 venv 未安装 playwright（`tools/capture_operations_screenshots.py` 依赖它，
且面向 A 负责人运维页面），因此改用 Edge headless 截图能力，并新增独立工具
`tools/render_b_demo_screenshots.py`；未修改 A 任务的截图工具。

**注意区分两层**：本报告只验证"引用可追溯"，**未验证"引用内容是否支持答案"**——
后者需要人工核验。

---

# 统一演示清单（2026-09-30 补充）

## 复现前置条件与命令

```powershell
cd D:\ICT\ai-security-intelligence-workbench-git

# 一键复现全部 5 个场景（内部自动使用数据库副本，真实库只读）
.\.venv\Scripts\python.exe tools\run_b_demo_evidence.py --out artifacts\b_eval\demo_evidence.json
```

* 前置条件：`.venv` 可用；`D:\ICT\intel-data-b\intel.sqlite` 存在。
* 脚本把库复制到 `%TEMP%\b_demo_*` 并把 `INTEL_DATA_DIR` 指向副本，**不会写真实库**。
* 未配置模型（`local_evidence_extraction`），检索为本地关键词 `keyword-v1`。

## 逐场景清单

| 场景 | 目标 | 输入问题 | 预期行为 | 运行 ID | 引用数 | 结果 | 截图 |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| DEMO-01 | 基础事实问答 | DistillGuard 这篇论文的标题是什么？ | 返回论文相关原文引用 | `run-124ed9b12439` | 5 | **成功**（原文摘录，非综合答案） | 缺失 |
| DEMO-02 | 多轮追问 | 它检测什么？（上一轮 DistillGuard） | 沿用上下文作答 | `run-9f802e61ccbe` | **0** | **失败**（RAG 不继承上下文，正确拒答） | 缺失 |
| DEMO-03 | 跨文档问答 | AUROC 在哪些文档中被讨论？ | 返回 ≥2 篇文档的引用 | `run-44937f5490a7` | 5 | **部分成功**（检索到多文档，**无综合**） | 缺失 |
| DEMO-04 | 证据不足拒答 | 明天的天气怎么样？ | 明确拒答 | `run-d388cbcb0c92` | 0 | **成功** | 缺失 |
| DEMO-05 | 引用定位与导出 | 什么是提示词注入？ | 引用可定位到原文 | `run-89a8e774a919` | 6 | **成功**（含字符区间） | 缺失 |

证据 ID 示例（完整列表见 `artifacts/b_eval/demo_evidence.json`）：

* DEMO-01 首个引用：`chunk-1e26fb499bb6dbae04a358d4`（doc-6848cfa4c508d3d98cbcc747，字符 23478–24466）
* DEMO-03 首个引用：`chunk-2c548b7cb0cbd3d90614329e`（doc-38443598019e64691b4f66e4，字符 186074–187052）
* DEMO-05 首个引用：`chunk-90c768cd5de7c577f26397d2`（doc-86fb37ed00532831b8e67acb，字符 816–1447）

## 截图状态：不可用（本轮再次确认）

`.venv` 中**没有** `playwright`、**没有** `selenium`；`%LOCALAPPDATA%\ms-playwright`
浏览器缓存**不存在**；PATH 上也没有 Chrome / Edge。

按边界要求**不安装大型依赖**，因此 `screenshot = "not_captured"`，
**未生成也未伪造任何截图**。替代证据是可复现的输入问题、完整答案、运行 ID、
引用的 `chunk_id` 与字符区间 —— 人工可在本地重跑复现。

## 可复现性说明

* 5 个场景共用同一脚本与同一批固定问题；重跑会产生**新的 run_id**（流水号不同），
  但输入、引用文档与证据结构一致。
* DEMO-02 的失败是**诚实性要求**的体现：能力不足时如实记录，不改写演示文本。
