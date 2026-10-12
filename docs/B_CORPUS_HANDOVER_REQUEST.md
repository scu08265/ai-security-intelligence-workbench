# B 项语料交接请求（2026-10-12）

> **状态：已交付并核验（2026-10-12 晚）**
>
> B 发来 `B_CORPUS_20261012.zip`，整包 SHA-256 `3aa9e9be1a76d4456f3f0f2db0481893381814b0369a1ed25ecffeeaf9e76e42`，
> 与约定值一致。解压后按 `MANIFEST.sha256` 逐文件核对 **47 / 47 通过**（哈希与字节数全对），
> 已还原到测试写死的 `D:\ICT\intel-data-b`（`intel.sqlite` = 8,183,808 B /
> `4095a5b1ff836f70baf5552304aac95f7eab5ee95fb3a58c45768e3478254285`，与文档记录一致）。
>
> 效果：测试从 **618 passed / 60 skipped** 变为 **674 passed / 4 skipped**。剩余 4 条跳过正是本节
> 第 2 节标注的两个**未随包提供**的衍生副本：`D:\ICT\intel-data-b-cvss-20261006`（3 条）与
> `D:\ICT\intel-data-b-poc-20261002`（1 条）。要清掉这 4 条，还需要 B 补这两个目录。
>
> 中频词那条已知失败用例已经定位并修复，见 `CHANGELOG.md` 与下文第 5 节。

## 1. 为什么要这份文件

B 项的关系 / 问答 / RAG 评测语料 `D:\ICT\intel-data-b\intel.sqlite` **只存在于 B 的机器上**。
2026-10-12 在交付机上复核过三条：

1. `D:\ICT` 目录不存在，D 盘下没有任何叫 `intel-data*` 的目录；
2. 全工作区扫描到的 6 个 sqlite 里，语料最多的是 1 个文档 / 849 分块（`official:eu_ai_act`），
   不是 B 那套 `paper:*`、约 3639 分块的评测语料；
3. 仓库里没有：412 个跟踪文件，没有任何 `.sqlite` / `.db` / 压缩包，也没有 `data/` 目录。
   `.gitignore` 明确排除 `data/*.sqlite*` 与 `artifacts/*/data/`，所以它**从设计上就不进仓库**。

这不是谁忘了提交，而是"数据不进仓库"这条约定的必然结果。代价是：语料一旦不在手上，
B 项的数字就只能被引用、不能被复核。

## 2. 请求交接的内容

| 优先级 | 文件 | 记录中的指纹 | 用途 |
| --- | --- | --- | --- |
| 必须 | `D:\ICT\intel-data-b\intel.sqlite` | 8,183,808 B / SHA-256 `4095a5b1…8254285`（见 `docs/B_BASIC_METRICS_ACCEPTANCE.md`） | 关系评测、正式问答集、RAG 检索与中频回归的唯一语料 |
| 建议 | `D:\ICT\intel-data-b-backups\intel-before-phaseB-20260930-094325.sqlite` | 见 `docs/B_DATA_READINESS.md` | 复核"零写入"声明与前后对比 |
| 可选 | `snapshots/` 目录（若与库分离存放） | 无 | 语料分块来自原始快照，只有库没有快照时无法重建 RAG 索引 |

**传输方式**：网盘 / 微信 / 移动硬盘都可以，主库只有约 8 MB。**不要走 git**——按 `.gitignore`
约定数据不入库，硬提交会把仓库撑大并且违反既有约定。

## 3. 到货后放在哪里

现有测试与工具把路径写死为 `D:\ICT\intel-data-b`，所以最省事的方式是在交付机上原样放回：

```powershell
(Get-Item -LiteralPath 'D:\ICT\intel-data-b\intel.sqlite').Length   # 期望 8183808
(Get-FileHash -LiteralPath 'D:\ICT\intel-data-b\intel.sqlite' -Algorithm SHA256).Hash
```

哈希与记录不符时**不要直接拿来跑评测**：先确认拿到的是不是同一份，否则评测数字对不上旧报告，
反而更难解释。

## 4. 语料到位后能解锁什么

| 解锁项 | 现状 | 到位后 |
| --- | --- | --- |
| 关系评测复现 | 数字只能引用 | 可重跑，可核对 TP/FP/FN |
| 正式问答集（50 题） | 跳过 3 条 | 可跑 |
| RAG 检索评测 | 跳过 30 条 | 可跑 |
| 混合语言查询与中频词回归 | 跳过 20 条，其中一条是**已知失败用例** | 可定位是哪一层掉链子并修复验证 |

语料到位前，合计 **58 条**依赖它的测试在交付机上被跳过，"全量测试通过"这句话必须附带
"58 条因缺语料跳过"的说明才成立。语料到位后这 58 条里有 54 条转为实际运行并通过，
加上新增的不依赖语料的回归测试，全量为 **675 passed / 4 skipped**。

## 5. 同时请 A 做的事

`fix/a-rag-midfreq-regression` **在远端不存在**。2026-10-12 复核远端 6 个 head：
`main`、`release/v0.2.2`、`feat/a-disposition-evidence-20261004`、
`feat/a-disposition-live-evidence-20261008`、`backup/remote-main-before-022-20260930`、
`chore/a-ci-validation-refresh`。没有任何一个是中频回归分支，所以该修复目前只在 A 的机器上，
交付机看不到也无法复核，请先推到远端。

**中频词回归：已定位并修复（2026-10-12）**。诊断脚本在真实语料上给出的结论是：**问题不在
`len(chunks) // 10` 这个判据**——`kernel-level`（df 9.0%）本来就通过守卫并命中。失败的是
`multi-agent` 那个用例，而且输在排序：`论文` 会扩展成 `paper / study / arxiv` 三个同义词，
它们在打分时各自独立计分，于是一篇只写了 "paper" 的论文能拿到约 10 分，而真正的主题词
`multi-agent` 只有约 2.5 分，把真正讨论 multi-agent 的那篇挤出了前 8。同一句话换成
“文章”或“文档”（不触发扩展）就排第一，可复现。

修法是把一个中文短语的同义词组按**一个概念**计分、取其中最强的一个，而不是每个同义词各算一份。
改动在 `app/rag.py`，`tests/test_rag_mixed_language_query.py` 全绿，全量 674 passed / 4 skipped。
因此 `// 10` 那条阈值可以维持现状；如果后续仍想在别的语料上稳健，再单独讨论。

## 6. 如果语料确实拿不到了

那就不要在报告里声称"B 项评测已复现"。可行的替代是把口径改成：

- 报告里保留 B 的历史评测数字，并逐条标注"B 机器语料、交付机未复现"；
- 在测试章节如实列出 58 条跳过及其原因（见 `docs/METRICS_BASELINE.md` 第 3 节）；
- 完成度按"代码路径已交付、评测数据未交付"来表述，而不是按"全部通过"来表述。
