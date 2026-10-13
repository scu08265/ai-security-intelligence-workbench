# 案例：一条漏洞情报的自动富化与关联推理

**用途**：对应赛题"富化信息准确且含自动关联推理"这一条。老师要求"准确最好有具体数值、自动关联推理要有一个案例"，
本文件给出一个**可在交付机上复现**的真实案例，以及每个字段的证据锚点。

**口径**：数据取交付机 `data/intel.sqlite`（2026-10-13 快照）。案例事件未做任何人工修饰，
所有字段都带 `source_id`，可以逐条回读原始快照。

## 1. 链路

```
登记来源 ──采集──▶ 原始快照 ──归一化──▶ 事件 ──富化──▶ CVSS / 受影响区间 / 修复版本
                                              └──▶ 论文关联（论文类事件）
                                              └──▶ 资产研判（有资产清单时）
                                              └──▶ 处置建议（策略感知，不声称个性化）
```

关联推理的关键约束：**每一步都必须带来源标识**。系统不会用模型补写缺失字段，
缺就是缺——这也是为什么 POC 与资产两个维度在评测语料上显示"无数据"而不是 0
（见 `docs/B_DIMENSION_SCOPE_POC_ASSET.md`）。

## 2. 真实案例：GHSA-w794-rj3p-xv45

事件：`GHSA-w794-rj3p-xv45`，标题 "Langflow: OS command injection (RCE) via arbitrary command in
MCP stdio server configuration"，组件 / 生态 `langflow / pip`。

| 富化维度 | 实际值 | 证据锚点 |
| --- | --- | --- |
| 来源 | GitHub Advisory（GHSA） | `sources[0].id = ghsa:4e843b5377`，URL `https://github.com/advisories/GHSA-w794-rj3p-xv45` |
| CVSS | 3.1 / **9.9** / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H` | `cvss[0].source_id = ghsa:df7a0000f5` |
| 受影响区间 | `>= 1.1.2, < 1.10.3`；`>= 0.1.2, < 0.10.3`；`< 1.10.3` | `affected[*].source_id = ghsa:02aa7802f6 / ghsa:88197e33c9 / ghsa:6b7e06787b` |
| 修复版本 | `1.10.3` 与 `0.10.3` 两条分支 | 与受影响区间同一 `source_id` 成对出现 |
| 关系 | 此事件无带证据的显式关系（`relationships = []`） | 未识别到跨文档关系时不补写 |

**关联推理体现在哪里**：三个 `affected` 条目对应**两条不同的版本线**（1.x 与 0.x），各自带独立的
`source_id` 和各自的修复版本。系统没有把三条区间合并成一条"看起来更整洁"的结论——
合并会让 0.x 线的用户拿到错误的修复版本。这正是"关联"而不是"汇总"：
同一事件下的证据按来源分别保留，再由研判逻辑判断哪一条适用于当前资产版本。

## 3. 富化准确率的数值怎么给

老师要求"关于准确，最好能有具体的数值"。现有可给的数值：

| 指标 | 数值 | 口径 |
| --- | --- | --- |
| 关系抽取 Precision | **1.0** | 抽样穷尽金标准，94 条可判定样本，FP=0 |
| 关系抽取 Recall | 0.734 | 同上范围，FN=25（version_range 12 + fixed_version 13） |
| 富化维度覆盖率（演示机） | cvss 65.1%、论文关联 25.2%、fixed_version 17.0%、poc 12.4%、资产研判 8.1%、关系证据 4.4% | `/api/competition/scorecard → enrichment.dimensions` |

**不能给的**：全语料召回率、POC 准确率、资产关联准确率。前两者缺分母，第三者只有合成资产。
报告里这三项写"无数据 / 不适用"，不写 0。

## 4. 复现方式

```powershell
# 维度覆盖率
.\.venv\Scripts\python.exe -c "import sys,json;sys.path.insert(0,'.');from app import competition_scorecard as c;print(json.dumps(c.scorecard()['enrichment']['dimensions'],ensure_ascii=False,indent=1))"

# 案例事件本体（含每条证据的 source_id）
.\.venv\Scripts\python.exe -c "import sys,json;sys.path.insert(0,'.');from app import storage;e=[x for x in storage.list_events(limit=None)[0] if x['id']=='GHSA-w794-rj3p-xv45'][0];print(json.dumps({k:e.get(k) for k in ('id','cvss','affected','sources')},ensure_ascii=False,indent=1))"
```

## 5. 边界（与证据一起引用）

- 本案例的 CVSS 与版本区间来自 **GitHub Advisory 单一来源**，不是 NVD 复核后的结论；
  系统如实保留 `source_id`，不把单来源值写成"权威评分"。
- 关系维度只覆盖四个维度（`paper_link` / `version_range` / `fixed_version` / `cvss`），
  `poc` 与 `asset_assessment` 在评测语料中无候选，原因是数据缺失而非能力缺失。
- 跨文档关系仍缺 52 条 document→document 边，因此本案例只演示"同事件内多来源关联"，
  不声称已具备完整跨文档推理。
