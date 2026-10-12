# 任务书 2026-10-12（队长）

**本文件当前基线的三个事实**（写任务的前提，组员请先对齐）：

1. 远端 `main` = `9ff7383`。B 的评测语料已交付并核验：`D:\ICT\intel-data-b`，
   `intel.sqlite` = 8,183,808 B / `4095a5b1…8254285`，47 个文件按 `MANIFEST.sha256` 全部通过。
2. 交付机上全量测试为 **675 passed / 4 skipped**（语料到位前是 618 / 60）。
3. 指标口径唯一基线 = 交付机 `data/intel.sqlite`，见 `docs/METRICS_BASELINE.md`。

---

## 一、组员 A（监测、性能与工程化）

### A1（最高优先）关闭"中频词检索回归"这条线

**结论先行**：诊断已经做完，问题**不在** `len(chunks) // 10` 这个阈值——`kernel-level`（df 9.0%）
本来就通过守卫并正常命中。真正失败的只有 `multi-agent` 那条，而且是输在**排序**：
`论文` 会扩展成 `paper / study / arxiv` 三个同义词，打分时每个同义词各自独立计一分，
于是一篇只写了 "paper" 的论文能拿到约 10 分，真正的主题词 `multi-agent` 只有约 2.5 分，
把真正讨论 multi-agent 的那篇挤出了前 8。同一句话换成"文章"或"文档"（不触发扩展）就排第一，可复现。

修复已在 `main`（`9ff7383`）：`app/rag.py` 里一个中文短语的同义词组按**一个概念**计分，
取其中最强的一个成员，而不是每个同义词各算一份。

**要做**：

1. `fix/a-rag-midfreq-regression` **废弃或 rebase**。不要按"调阈值"的方向继续改。
2. 在你自己机器上（有语料）复验，贴出两条命令的输出：

   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_rag_mixed_language_query.py -q
   .\.venv\Scripts\python.exe tools\diagnose_rag_midfreq.py
   ```

   期望：前者全绿；后者两个用例都是 `-> passes`（不再是 `-> retrieval`）。
3. 走查 `app/rag.py` 的这次改动，确认没有别的调用点依赖"同义词逐词计分"的旧行为。

**验收**：上面两条命令的输出 + 一处确认；**不改** `// 10`。

### A2 把 CI 证据刷新到当前 head

`reports/ci-validation.json` 还指向 `8db19cf`（2026-10-02），远端那个没合的
`chore/a-ci-validation-refresh` 也只刷到 `b020090`（2026-10-10），而当前 `main` 是 `9ff7383`。

**要做**：在最新 `main` 上触发一次 CI，把 `run_id / head_sha / updated_at` 与
`test`、`container`、`rollback` 三个 job 的结论写回 `reports/ci-validation.json`；
同时把 `chore/a-ci-validation-refresh` 合掉或删掉，别留过期分支。

**验收**：该文件的 `head_sha` 等于当时的 `main`，三个 job 均 `success`。

### A3 处置闭环证据与交付口径对齐

你那份 live 证据里的"生产库"是 `D:\新建文件夹\2026-09-26\ba\ai-security-intelligence-workbench\data\intel.sqlite`，
那是你机器上的另一份库，交付机上不存在，因此 `4 / 3 / 0.75` 在交付机无法复现。

**要做**：

1. 所有引用该证据的文档加运行环境限定语，规则见 `docs/METRICS_BASELINE.md` 第 3 节。
2. 若要保留 "live" 这个说法，就在交付机上重跑：用 `data/intel.sqlite` 的副本、走同样两条真实 HTTP 路由
   （`/api/dispositions/metrics`、`/api/competition/scorecard`），产出新证据，让页面 / 接口 / 证据三者同源。
3. 交付口径的闭环率写交付机的 `48 / 4 / 8.33%`。

**验收**：文档里不再出现未加限定语的 `0.75`；或交付机上有可复现的新证据。

### A4（低优先）Docker 验收的一致性复核

本地两步验收已跑通（`docs/DOCKER_CI_GUIDE.md` 第 7 节），期间修了三个脚本缺陷：docker 路径写死成
`C:\Program Files`、等待用了在 stdin 被重定向时会立刻退出的 `timeout`、以及缺 `--build-arg APP_VERSION`
导致容器报 0.2.3 而仓库是 0.2.4。另外加了凭据检查——`docker compose config` 与 `docker inspect`
会把 `.env` 里的 token 抄进入库日志，GitHub push protection 会直接拒收。

**要做**：在你自己机器上按第 7 节复跑一次，确认九项检查与产物一致；核对 CI 的 `container` job 与本地脚本同源。

### A5 明确不做

不要改 `app/rag.py` 里的 `max(1, len(chunks) // 10)`。已实测它不是本次问题的原因；
若以后要在别的语料上求稳健，单独开一条讨论。

---

## 二、组员 B（RAG / 关系 / 问答评测）

### B1（最高优先）补两个衍生副本

这次交付的包不含这两个目录，交付机上对应 4 条测试跳过：

| 目录 | 规模 | 解除的跳过 |
| --- | --- | --- |
| `D:\ICT\intel-data-b-cvss-20261006` | 49 文件 / 51,696,151 B | `test_b_relation_cvss_recheck.py`（2）+ `test_b_relation_expansion.py`（1） |
| `D:\ICT\intel-data-b-poc-20261002` | 90 文件 / 80,776,330 B | `test_b_reeval_20261002.py`（1） |

**要做**：按上次同样的方式打包——整包给一个 SHA-256，包内放 `MANIFEST.sha256`，
每行格式 `<SHA256>  <字节数>  <相对路径>`；**不要动源目录**，也不要提交进仓库。

**验收**：我这边逐文件核对通过；跑完上述三个测试文件后，全量跳过数从 **4 降到 0**。

### B2 把"因缺语料未复现"的结论刷新为"已在交付机复现"

语料到位后，`test_rag_retrieval_b_task.py`（30 条）、`test_rag_mixed_language_query.py`（20 条）、
`test_b_formal_qa_set.py`（3 条）、`test_b_multihop_candidates.py`（1 条）都已实际运行并通过，
后者的中频词用例也随 A1 的修复转绿。

**要做**：按 `docs/METRICS_BASELINE.md` 的引用规则，更新 `docs/B_EVIDENCE_INDEX.md` 及相关报告里的措辞，
把"这套数字只能在 B 机器上成立"改成"已交付并在交付机复现，语料经哈希核验、不入库"。

**验收**：不再有"交付机无法复现"的旧表述。

### B3 把 POC / 资产两个维度说清楚：是缺数据，不是缺代码

交付语料的实测（2026-10-12，只读查库）：

| 项 | 值 |
| --- | --- |
| events / event_aliases | 93 / 15 |
| rag_documents / rag_chunks | 22 / 3639 |
| **assets / assessments** | **0 / 0** |
| **events 含 `poc[]`** | **0** |
| events 含 `cvss[]` | 22 |

也就是说 POC 与资产关联这两项在这份语料里**根本没有数据**，这跟缺那两个衍生副本是两件事。

**要做**：出一份口径说明（一两页）：这两个维度各自的数据来源是什么、能否补、补不上时报告怎么写。
补不上就写"无数据"，**不要写 0**——0 分和"没有分母"是两种含义。

**验收**：一句话能回答"POC 维度为什么没指标"。

### B4 中频词修复后的重跑确认

`app/rag.py` 的排序计分变了，虽然只影响同义词扩展，但问答的引用集合可能间接变化。

**要做**：用原语料重跑关系 / 问答 / RAG 评测，确认已交付 artifact 的数字没有漂移。
若漂移，更新 artifact 并说明是哪一项、为什么。

**验收**：重跑后的数字与 `artifacts/b_eval/` 一致，或有明确的变更说明。

### B5 明确不做

不要把语料或压缩包提交进仓库。`.gitignore` 排除 `data/*.sqlite*` 与 `artifacts/*/data/` 是既定约定，
交付方式就是整包外发 + 哈希核验。
