# B 任务审计报告

| 项 | 值 |
| --- | --- |
| 审计范围 | 仅 B 任务（富化评测、跨文档与多跳评测、问答评测、策略感知处置建议、演示与交付证据） |
| 审计日期 | 2026-09-30 |
| 审计方式 | 静态代码阅读 + 只读实测（未修改任何源码） |
| 审计基线 | 分支 `feat/b-evaluation` @ `3dc91b17995002f0a0d8c9e4ea76317b270e8146` |
| 对应远端 | `https://github.com/scu08265/ai-security-intelligence-workbench.git` |

---

## 1. 审计范围与边界

### 1.1 范围内

- `app/evaluation.py`、`app/eval_dataset.py`、`app/competition_scorecard.py`
- `evaluation/` 下的评测数据集
- `tests/` 中与评测、问答、资产研判相关的测试
- 资产处置建议相关的现有接口（`app/intelligence.py`、`app/cyclonedx_assets.py`、`app/api.py`、`app/storage.py`）
- B 任务演示所需的截图工具、证据产物与导出接口
- B 任务后续实施所需的依赖与运行命令

### 1.2 范围外（本次不做，也不评价）

- A 任务产线：`app/reliability.py`、`app/scheduled_job.py`、`app/observability.py`、`scripts/`、`.github/workflows/ci.yml`、`reports/` 的生成逻辑
- `app/multi_agent_runtime.py`、`app/self_healing.py`（归属其他成员，仅在涉及评测对象时说明）
- `app/streaming.py`、前端交互实现的整体评价
- 赛题其他模块（采集器实现细节、去重算法、部署工程化）

### 1.3 审计方式与操作限制

本报告所有数字均来自本次只读实测，未做任何估算或推断填充。唯一执行的动作是运行测试套件，且使用了禁写标志：

```powershell
$env:PYTHONDONTWRITEBYTECODE=1
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

该方式不产生 `__pycache__`，也不产生 `.pytest_cache`。测试本身通过 `tests/conftest.py` 把数据目录指向临时目录、删除模型密钥、禁用网络，因此不会写入仓库。

本次审计**未修改、未删除任何既有文件**；`docs/B_TASK_AUDIT.md` 是唯一新增文件。

### 1.4 仓库状态（实测）

| 项 | 实测结果 |
| --- | --- |
| 当前分支 | `feat/b-evaluation` |
| HEAD | `3dc91b1` |
| `main` / `origin/main` | 同一 commit `3dc91b1` |
| `main...feat/b-evaluation` | `0  0`（无领先、无落后） |
| 暂存区 | 空 |
| 工作区未提交改动 | 无源码改动 |
| 未跟踪文件 | 仅 `.idea/` 下 6 个 PyCharm 配置文件（IDE 生成，非源码） |

### 1.5 关于未提交修改

B 任务相关文件（`app/evaluation.py`、`app/eval_dataset.py`、`app/competition_scorecard.py`、`app/intelligence.py`、`app/cyclonedx_assets.py`、`evaluation/`、`tests/`）经 `git status` 核对，**没有任何未提交修改**。

工作区现有的唯一未跟踪项是 `.idea/` 目录（`.gitignore` 未忽略它，但它属于 IDE 配置，非 B 任务产物）。**本次未清理、未覆盖、未改动它。**

---

## 2. B 任务各项要求与当前实现状态

状态定义见附录 A。

### 2.1 任务 1 · 富化准确率与召回率评测

| 子要求 | 状态 | 依据 |
| --- | --- | --- |
| 六个维度存在覆盖率统计 | ✅ 已实现 | `app/competition_scorecard.py::_enrichment_metrics` |
| 至少 100 条经核验的标注关系 | ❌ 未实现 | 全仓库无富化金标准数据集 |
| 分维度 precision / recall | ❌ 未实现 | 只有 `coverage`（维度是否有值） |
| TP / FP / FN 明细 | ❌ 未实现 | 无 |
| 微平均 / 宏平均 | ❌ 未实现 | 无 |
| 未知样本与正负例区分 | ❌ 未实现 | 现有实现把"有值/无值"二分，无 unknown 概念 |

**关键区分**：现有六个维度统计的是**覆盖率**（该维度有没有值），**不是准确率或召回率**。项目自身的规划文档也明确承认这一点（`docs/AGENT_UPGRADE_PLAN.md` §11.3："当前'维度是否有值'是覆盖率，不是准确率或召回率"）。

### 2.2 任务 2 · 跨文档与多跳推理评测

| 子要求 | 状态 | 依据 |
| --- | --- | --- |
| 至少 30 道评测题（文档/实体/关系边/证据 ID/标准答案） | ❌ 未实现 | `evaluation/` 下只有 `gold_cases.json` |
| 真实关系路径搜索 | ❌ 未实现 | `app/intelligence.py` 内无路径搜索函数 |
| 结构化证据链输出 | ❌ 未实现 | 无理由图/路径结构 |
| 测量当前系统基线 | ❌ 未实现 | 无多跳基线记录 |
| 不把预存关系格式化冒充多跳 | — | 现有实现确为**预存关系格式化**，见下 |

现有相关代码只有一处：`app/intelligence.py` 第 458 行附近，从 `event["relationships"]` 中筛选带 `evidence_ids` 的关系并格式化为"主体 → 关系 → 客体"文本。这是**已有关系的呈现**，不构成在线路径搜索或跨文档推理。

全仓库检索 `multi_hop|multi-hop|多跳|reasoning_path|path_search`，命中的全部是文档（`docs/AGENT_UPGRADE_PLAN.md` 12 处、`docs/AUDIT_QA_AGENT_CAPABILITIES.md` 8 处、`docs/COMPETITION_UI_REQUIREMENTS.md` 3 处）、一处前端文案（`app/static/app.js`）和一处测试断言（`tests/test_product_ui.py`），**无任何实现代码**。

### 2.3 任务 3 · 问答评测

| 子要求 | 状态 | 依据 |
| --- | --- | --- |
| 固定评测集 | 🟡 部分实现 | `evaluation/gold_cases.json`，仅 4 条 |
| 答案准确率 | ✅ 已实现 | `app/eval_dataset.py::score_records` |
| 引用准确率 | ✅ 已实现 | 同上（但分母仅 1） |
| 拒答准确率 | ✅ 已实现 | 同上 |
| 分母分项统计 | ✅ 已实现 | `score_records` 返回独立的 `counts` |
| P50 / P95 | ❌ 未实现 | 只有 `average` 与 `maximum` |
| 超时统计 | ❌ 未实现 | 无超时概念 |
| 失败样本明细 | ❌ 未实现 | 只落 `details[].retrieved` |
| 对照 75% / 90% / 95% 分档 | ❌ 未实现 | 无分档函数 |
| 覆盖基础/语义/多轮/跨文档/多跳/拒答六类 | 🟡 部分实现 | 现有 4 条覆盖检索、修复版本、多轮、拒答；缺语义、跨文档、多跳 |
| 样本不足时报告"不可评测" | ❌ 未实现 | 极小分母仍照常输出数值 |

### 2.4 任务 4 · 策略感知资产处置建议

| 子要求 | 状态 | 依据 |
| --- | --- | --- |
| 四档影响结论 | ✅ 已实现 | `app/intelligence.py::assess_asset` |
| 结论带判定理由与证据 ID | ✅ 已实现 | 同上，返回 `reasons` / `evidence_ids` |
| 优先级排序 | 🟡 部分实现 | `_priority()` 只用 severity / CVSS / business_criticality / exposure |
| 维护窗口 | ❌ 未实现 | 全仓库无相关字段 |
| 禁止动作 | ❌ 未实现 | 无 |
| 负责人 | ❌ 未实现 | 无 |
| 可接受停机 | ❌ 未实现 | 无 |
| 排序因子可解释 | 🟡 部分实现 | 有 reasons，但未解释排序权重 |
| 不虚报个性化推荐 | — | 现有代码/界面未出现"个性化推荐"表述，符合要求 |

关于"维护窗口""负责人"两个关键词的检索命中，经逐条核对**均为无关字符串**：

- `tests/fixtures.py:159`：`"Unrelated synthetic maintenance note"`，是一个 RSS 测试条目的标题
- `app/normalize.py:1101`：`"研究负责人已核验的…"`，是一句 reason 文本

两者都不是功能实现。

### 2.5 任务 5 · 演示与交付证据

| 子要求 | 状态 | 依据 |
| --- | --- | --- |
| 截图工具 | 🟡 部分实现 | `tools/capture_operations_screenshots.py` 存在，属 A 任务产线 |
| 已有截图 | 🟡 部分实现 | `docs/screenshots/` 下 5 张（health / reliability / scorecard / reports / ci），偏运维视角 |
| 运行记录接口 | ✅ 已实现 | `GET /api/runs`、`storage.save_run` |
| 导出接口 | ✅ 已实现 | `GET /api/export` → `storage.export_snapshot()` |
| 基础问答演示脚本 | ❌ 未实现 | 无 |
| 多轮问答演示脚本 | ❌ 未实现 | 无 |
| 跨文档推理演示脚本 | ❌ 未实现 | 无 |
| 运行 ID / 证据 ID 留存流程 | ❌ 未实现 | 无固定流程与产物 |

---

## 3. 对应代码路径与实际验证证据

### 3.1 评测主链路

| 路径 | 作用 | 本次验证方式 |
| --- | --- | --- |
| `app/evaluation.py` | 本地金标准回归，30 条用例 | 静态阅读 + 隔离环境实跑 |
| `app/eval_dataset.py` | 标注集加载与打分器 | 静态阅读 |
| `app/competition_scorecard.py` | 赛题指标投影 | 静态阅读 |
| `evaluation/gold_cases.json` | 标注问答集（4 条） | 读取并核对条数与字段 |
| `research/cases.json` | 真实核验案例（3 条） | 读取并核对条数与字段 |
| `tests/test_eval_dataset.py` | 打分器测试（3 项） | 随全量套件执行 |
| `tests/test_competition_scorecard.py` | 指标投影测试（7 项） | 随全量套件执行 |

### 3.2 实测证据

**证据 1 · 全量测试套件**

```
278 passed, 1 warning in 84.58s
```

环境：仓库自带 `.venv`，Python 3.13.7，pytest 9.1.1。唯一告警是 `fastapi.testclient` 的 `StarletteDeprecationWarning`（第三方库告警，与本任务无关）。

**证据 2 · 空数据库下运行 `run_evaluation()`**

在全新临时数据目录（`INTEL_DATA_DIR` 指向 tmp，事件数为 0）下执行本地回归，实测输出：

| 指标 | 实测值 |
| --- | --- |
| `cases_total` | 30 |
| `cases_passed` | 30 |
| `real_case_count` | 24 |
| `synthetic_case_count` | 6 |
| `retrieval_precision` | 1.0 |
| `retrieval_recall` | 0.3333 |
| `answer_accuracy` | 0.3333 |
| `citation_accuracy` | 1.0 |
| `refusal_accuracy` | 0.5 |
| `labelled_counts` | `{"retrieval_tp": 1, "retrieval_fp": 0, "retrieval_fn": 2, "answer_cases": 3, "citation_cases": 1, "refusal_cases": 4}` |
| `qa_response_duration_ms` | `{"samples": 4, "average": 0.137, "maximum": 0.204}` |

**证据 3 · 30 条回归用例不再依赖数据库（相对早期版本的改进）**

`app/evaluation.py::_make_cases()` 现在直接读取 `research/cases.json` 并调用 `normalize.research_case_to_event()`，不再从数据库按 `verified_research` 标签筛选。因此**空数据库下 30 条用例仍全部通过**（见证据 2）。这消除了"必须先初始化演示数据才能评测"的顺序依赖。

但**标注问答指标仍依赖数据库**：`run_evaluation()` 内部调用 `run_labelled_evaluation(stored_events, storage.list_assets())`，而 `stored_events` 来自 `storage.list_events()`。仓库中不存在 `data/` 目录（`.gitignore` 忽略 `data/*.sqlite*`、`data/snapshots/`、`data/evidence/`），**任何干净克隆的数据库都是空的**，此时标注指标会退化（见证据 2）。

**证据 4 · 仓库内无运行时数据**

```
Test-Path data/  ->  False
```

---

## 4. 已发现的 Bug、复现步骤与影响

### Bug B-01 · `_make_cases()` 中两个闭包错误引用循环变量（潜伏型）

**位置**

| 行号 | 代码 | 状态 |
| --- | --- | --- |
| `app/evaluation.py:129` | `def version_inside(event=event, inside=inside):` | 正确 |
| `app/evaluation.py:134` | `def version_outside(event=event, outside=outside):` | 正确 |
| `app/evaluation.py:148` | `def unknown_version(event=event):` | 不使用该变量 |
| `app/evaluation.py:153` | `def missing_condition(event=event, inside=inside):` | 已修复 |
| **`app/evaluation.py:161-162`** | **`def out_of_scope(event=event):`** → 第 162 行使用裸 `inside` | **缺陷** |
| **`app/evaluation.py:167-171`** | **`def withdrawn(event=event):`** → 第 171 行使用裸 `inside` | **缺陷** |
| `app/evaluation.py:175` | `def attack_chain(event=event, event_id=event_id):` | 正确 |
| `app/evaluation.py:184` | `def enrichment_gaps(event=event):` | 不使用该变量 |

`inside` 是 `for event in research:` 循环内的局部变量。未作为默认参数绑定的闭包在**调用时**才解析该名字，因此取到的是循环结束后的最终值（最后一条案例的 `inside`）。

**预期行为**

| 事件 | 应传入的版本 |
| --- | --- |
| `CVE-2026-7482` | `0.17.0` |
| `CVE-2026-22778` | `0.14.0` |
| `CVE-2026-54235` | `0.8.5` |

**复现步骤**

1. 前提：`research/cases.json` 中存在 ≥2 个能推导出 probe 版本的研究案例，且它们的 `inside` 互不相同（当前 3 条均满足）。
2. 用 monkeypatch 拦截 `app.intelligence.assess_asset`，记录 `(event["id"], asset["version"])`。
3. 调用 `app.evaluation._make_cases()`，对 id 以 `::out-of-scope` 或 `::withdrawn` 结尾的用例执行 `case.check()`。
4. 观察记录的版本。

**实测结果**

```
1. CVE-2026-7482    version=0.8.5   kind=out-of-scope
2. CVE-2026-7482    version=0.8.5   kind=withdrawn
3. CVE-2026-22778   version=0.8.5   kind=out-of-scope
4. CVE-2026-22778   version=0.8.5   kind=withdrawn
5. CVE-2026-54235   version=0.8.5   kind=out-of-scope
6. CVE-2026-54235   version=0.8.5   kind=withdrawn
```

6 次调用全部使用 `0.8.5`，即循环最后一条案例的值。前两条事件各取错了版本。

**影响定性（不夸大）**

`app/intelligence.py::assess_asset` 的短路顺序为：

```
事件已撤回            -> needs_confirmation     （在版本逻辑之前）
资产未授权            -> not_applicable         （在版本逻辑之前）
否则                  -> 版本比较 + 条件判断
```

因此：

- 这**不是产品功能缺陷**。对撤回事件和未授权资产，`assess_asset` 的返回是正确的。
- 这是**评测代码缺陷**：夹具参数错误，用例没有真正覆盖它声称的场景。
- **当前不改变任何 pass/fail**，属潜伏型问题。278 项测试全绿的同时该缺陷依然存在。
- **风险**：一旦短路顺序被调整，或有人新增依赖版本边界的授权用例，这两个用例会静默断言错误内容。该缺陷与第 153 行已经修好的 `missing_condition` 属同一类问题，是**修复未覆盖到的部分**。

**现有测试覆盖情况**

- `tests/test_intelligence.py:37` 直接验证了产品行为（撤回事件 → `needs_confirmation`），该用例有效。
- **没有任何测试覆盖 `_make_cases()` 的用例构造**，因此该缺陷无法被现有测试发现。

### 风险 B-02 · 极小分母下 `retrieval_precision` 返回 1.0

由证据 2：空数据库下 `retrieval_tp=1, retrieval_fp=0 → precision = 1.0`，而同一份结果里 `retrieval_recall=0.3333`。precision 的分母仅 1，数值本身不具代表性，且**报告中没有样本量下限或"不可评测"守卫**。

**影响**：单看 precision 会得出与 recall 相反的结论，存在被误读为达标的可能。

### 风险 B-03 · 空语料下的响应耗时失真

由证据 2：空数据库下 `qa_response_duration_ms.average = 0.137 ms`。该数值反映的是"未检索到任何证据"的执行时间，**不代表真实问答耗时**。若直接用于对照赛题 `≤5s` 分档，会得出无意义的结论。

`docs/AGENT_UPGRADE_PLAN.md` §11.4 已规定"超时和错误进入准确率与时延统计，不从分母剔除"，但当前实现既无超时概念，也无"语料为空"守卫。

---

## 5. 评测数据缺口、金标准质量与指标分母风险

### 5.1 数据缺口

| 数据集 | 当前规模 | B 任务目标 | 缺口 |
| --- | --- | --- | --- |
| 富化关系金标准 | 0 条（不存在） | ≥100 条 | 全部 |
| 跨文档 / 多跳题集 | 0 条（不存在） | ≥30 道 | 全部 |
| 标注问答集 `evaluation/gold_cases.json` | 4 条 | 50–100 条 | ≥46 条 |
| 真实核验案例 `research/cases.json` | 3 条 | 富化标注素材 | 严重不足 |

### 5.2 金标准质量

现有 `evaluation/gold_cases.json` 的 provenance 机制是**可信的**：`load_cases()` 强制每条用例声明 `provenance`，且限定为 `real_verified` 或 `synthetic_regression`，否则抛错。

当前 4 条构成：

| provenance | 条数 | 说明 |
| --- | --- | --- |
| `real_verified` | 2 | 来自 `research/cases.json` 的真实核验案例 |
| `synthetic_regression` | 2 | 合成夹具 |

**注意**：`real_verified` 的"核验"是**项目团队自行核验**，不是第三方独立标注，也未做盲测。`app/evaluation.py` 的 limitations 字段已如实声明这一点。

为满足 B 任务要求，后续数据扩展需要引入第三类标记——**待核验（`pending_verification`）**：AI 可以辅助初标，但未经来源核验的内容不得标为真实金标准。

### 5.3 指标分母风险

由证据 2 的 `labelled_counts`：

| 指标 | 分母 | 风险 |
| --- | --- | --- |
| 检索 precision / recall | 3 个期望事件 | 单条改变即大幅波动 |
| 答案准确率 | 3 条 | 同上 |
| **引用准确率** | **1 条** | 对错即 0% 或 100%，无统计意义 |
| 拒答准确率 | 4 条 | 单条权重 25% |
| 响应时间 | 4 个样本 | 不足以支撑 P50/P95 |

### 5.4 POC 维度的结构性限制

`app/competition_scorecard.py::_enrichment_metrics` 中 `poc` 定义为 `bool(event.get("poc"))`，完全依赖采集到的真实 POC 数据。若来源未提供 POC，该维度的召回率会被结构性钉在 0，与标注质量无关。**该情况必须在报告中如实说明，不得通过修改判定逻辑提高数值。**

### 5.5 数据来源依赖

富化金标准与问答集必须建立在真实事件之上，而仓库中不存在 `data/`。因此在建立标注数据之前，**需要先执行一次真实采集**以获得可标注素材。金标准中的标识必须使用稳定 ID（CVE / GHSA / arXiv 编号），不得使用数据库自增 ID，否则换机器即失效。

---

## 6. 当前依赖与可复现命令

### 6.1 依赖现状

仓库自带 `.venv`（Python 3.13.7），运行时依赖已满足：

| 包 | 版本 | 状态 |
| --- | --- | --- |
| fastapi | 0.142.1 | 已安装 |
| pytest | 9.1.1 | 已安装 |
| httpx | 0.28.1 | 已安装 |
| pypdf | 6.19.0 | 已安装 |
| packaging | 26.3 | 已安装 |
| **playwright** | — | **未安装** |

**Playwright 现状**（仅任务 5 需要）：

| 项 | 状态 |
| --- | --- |
| `.venv` 中的 playwright 包 | 未安装 |
| chromium 二进制（`%LOCALAPPDATA%\ms-playwright`） | 不存在 |
| `requirements.txt` | 刻意不含 playwright（附注释说明） |
| `requirements-report.txt` | 单独列出可选依赖 `playwright>=1.50,<2` |
| `tools/capture_operations_screenshots.py` | 顶层硬 `import`，缺包时直接 ImportError，无友好降级 |

**结论：任务 5 需要安装 playwright 包与 chromium 浏览器二进制两样，且需联网。现阶段不安装。**

B 任务 1–4 项（评测类工作）**不需要任何新增依赖**，仅用标准库与 `packaging` 即可完成。

### 6.2 可复现命令

```powershell
cd D:\ICT\ai-security-intelligence-workbench-git

# 全量测试（本次实测：278 passed / 84.58s）
.\.venv\Scripts\python.exe -m pytest -q

# 只读方式运行，不产生 __pycache__ 与 .pytest_cache
$env:PYTHONDONTWRITEBYTECODE=1
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider

# 启动服务（A 任务文档使用 8010 端口）
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8010

# 评测相关接口
# GET  /api/evaluation        最近一次评测摘要
# POST /api/evaluation/run    执行本地回归
# GET  /api/competition/scorecard  赛题指标投影

# 任务 5 备用（需先安装 playwright + chromium）
.\.venv\Scripts\python.exe tools\capture_operations_screenshots.py --base http://127.0.0.1:8010
```

### 6.3 测试隔离性说明

`tests/conftest.py` 对每个用例建立独立临时数据目录，删除模型密钥与 `GITHUB_TOKEN`，把采集退避时间归零，因此测试套件**完全离线、确定性、不写仓库**。本次审计跑完测试后复查 `git status`，工作区仍未产生任何文件。

---

## 7. B 任务分阶段实施计划、验收标准与风险

实施顺序：**阶段 0 → 1 → 2 → 5 → 3 → 4**。每阶段完成后先汇报变更、测试结果、未解决问题与下一步，待确认后再进入下一阶段。

### 阶段 0 · 审计与准备（当前阶段）

- **产出**：本文件 `docs/B_TASK_AUDIT.md`。
- **验收标准**：仓库状态、能力分级、缺陷清单、数据缺口、依赖与命令、实施计划齐备，且每项结论可回溯到代码路径或实测证据。
- **风险**：无（纯只读 + 单文件新增）。

### 阶段 1 · 问答评测完善（优先做，见效最快）

- **改动范围**：`app/eval_dataset.py`、`evaluation/gold_cases.json`、`app/competition_scorecard.py`（接入）、`tests/test_eval_dataset.py`
- **内容**：题集扩到 50–100 条，覆盖基础/语义/多轮/跨文档/多跳/拒答六类；补 P50/P95、超时计数、失败样本明细；增加 75%/90%/95% 分档；增加"样本不足即报不可评测"的守卫。
- **验收标准**：六类题目各有明确分母；P50/P95 与超时/失败可从评估产物直接读取；未达样本下限时返回"不可评测"而非数值。
- **风险**：标注需要领域判断，AI 只能辅助初标；未经核验的不得标为真实金标准。

### 阶段 2 · 富化准确率与召回率

- **改动范围**：新增 `evaluation/enrichment_gold.json`、新增 `app/enrichment_eval.py`、`app/competition_scorecard.py`、新增 `tests/test_enrichment_eval.py`
- **内容**：≥100 条标注关系，六维度分别标注正例/负例/未知；分维度输出 precision、recall、TP、FP、FN；同时报告微平均与宏平均。
- **验收标准**：未知样本不参与正负例计算；每个数字可回溯到具体标注条目与来源链接；POC 维度若无有效样本，如实标注不可评测。
- **风险**：依赖真实采集数据；POC 维度可能结构性为 0；标注工作量最大。

### 阶段 5 · 演示与交付证据

- **改动范围**：新增演示脚本（路径待定）、复用 `tools/capture_operations_screenshots.py`
- **内容**：基础问答、多轮问答、跨文档推理三组证据，含运行 ID、证据 ID、截图、导出结果。
- **验收标准**：每步可复核；截图与实际运行记录一致；不出现无来源的结论。
- **风险**：需安装 playwright 包与 chromium 二进制（需联网，需单独申请）；跨文档证据受阶段 3 进度制约。

### 阶段 3 · 跨文档与多跳推理

- **改动范围**：新增 `evaluation/crossdoc_multi_hop.json`、新增关系路径搜索实现、新增 `tests/`
- **内容**：先建立 ≥30 道有来源、有标准答案的题集并测量**当前系统基线**；随后实现真实的关系路径搜索、证据链关联与结构化推理输出。
- **验收标准**：每题标注文档、实体、关系边、证据 ID 与标准答案；系统输出的每条边可打开原文证据；不以预存关系格式化冒充多跳推理；冲突来源不被静默合并。
- **风险**：**这是工作量最大且有前置依赖的一项**。现有实现只有关系格式化，无路径搜索；关系图密度是否支撑 30 道题尚需验证；可能需要补充带来源的关系数据。

### 阶段 4 · 策略感知资产处置建议

- **改动范围**（需先提交 schema 影响说明并协调 A 任务负责人）：

| 模块 | 影响 |
| --- | --- |
| `app/api.py::AssetRequest` | 新增策略字段；当前模型无 `extra="forbid"`，多余字段会被静默丢弃 |
| `app/api.py::_asset_payload` | 字段透传 |
| `app/storage.py::upsert_asset` | 落库字段与文档结构 |
| `app/cyclonedx_assets.py` | SBOM 导入时的字段默认值 |
| `app/intelligence.py::_priority` | 排序因子扩展 |
| `app/static/app.js` | 资产表单与展示（约 2418–2446 行区域） |

- **内容**：引入维护窗口、业务重要性、禁止动作、负责人、可接受停机；输出按策略排序并提供排序因子解释。
- **命名要求**：若达不到"个性化推荐"，输出统一称**"策略感知处置建议"**。
- **验收标准**：每条建议可回溯到资产事实与策略输入；排序因子可解释；不出现无依据的偏好推断。
- **风险**：**跨任务接口变更**。未经确认不得修改可能影响 A 任务的公共接口或数据结构。

---

## 附录 A · 状态定义

| 标记 | 定义 |
| --- | --- |
| ✅ 已实现 | 存在可运行实现，并有代码路径或实测证据支持 |
| 🟡 部分实现 | 存在实现但覆盖不全，或缺少关键组成 |
| ❌ 未实现 | 全仓库无实现代码 |
| 🔵 需验证 | 结论需进一步实验或需与相关方确认后才能定论 |

## 附录 B · 本次审计未做的事

- 未修改、未删除任何既有文件
- 未修改 `main`，未切换分支，未执行任何 git 写操作
- 未执行 `git add` / `commit` / `push` / `merge`
- 未安装任何依赖（含 playwright）
- 未清理 `.idea/` 或其他任何未跟踪文件
- 未评价 A 任务或其他成员负责的功能
- 报告内所有数字均来自本次实测；未实测项一律标为未实现或需验证，未做估算填充
