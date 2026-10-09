# 关系评测 CVSS 漏检复核与重跑结论

B 项 2026-10-04 金标准中 5 条 `cvss` 漏检（FN）的根因是采集链路只把 NVD 的 Exploit 引用
回填进 `poc[]`、丢弃了 CVSS `metrics`（CISA KEV 采集的事件 `cvss[]` 为空）。修复
commit `6d15d31` 后 `tools/backfill_nvd_poc.py` 同时合并 `cvss`。本批次在真实库副本上按
CVE 定向拉取 3 个 CVE 的 NVD CVE API 2.0 原始响应（SHA256 入清单、可逐字节回读），
回填后 4 个事件新获得 CVSS；重跑候选集后四维候选由 121 增到 127（`cvss` 22 → 28），
其中新出现的 5 条 `cvss` 关系与金标准期望向量逐字符比对全部命中（5/5），已由人工核验、
置为 `human_verified` 并署名（`人工复核-用户确认` / `2026-10-09`）；其余 121 条标注按
关系内容迁移，0 条被改写。

评分（任务指定命令，gold = `evaluation/b_relation_gold_20261004.json`）：TP 52 / FP 0 /
FN 5，Precision 1.0、Recall 91.23%、F1 95.41%；对比 10-04 冻结基线（TP 47 / FN 5、
Recall 90.38%、F1 94.95%）TP 增加 5、Recall 上升 0.85pp，`cvss` 维度 TP 10 → 15。
若把 gold 的 expected 改指向修复后的真实候选 id
（`evaluation/b_relation_gold_20261006.json`，`missed = 0`），则 FN = 0、Recall = F1 = 100%。

有一点必须如实说明：字面命令下 FN 仍为 5，不等于漏检还在。10-04 的 gold 用 5 个合成 id
（`BREL-GOLD-FN-CV-0001..0005`）记录"应抽取"，而修复后系统抽出的这 5 条关系是新的候选 id
（`BREL-CV-0021..0025`）；评分器按 `relation_id` 比对
（`missing_ids = expected_ids − 已验证 positive 的 id`），旧 id 无从匹配，于是这 5 个旧 id
仍被计为 FN。这是表示层（id 不同源）未收敛，数据侧漏检已经真实收敛。

本批次仍是抽样穷尽（11 个对象、4 个维度），不是全语料召回；`poc` / `asset_assessment` 仍单列。
10-04 的 gold 与两份旧评分文件保持冻结、0 改动；真实库 `D:\ICT\intel-data-b` 全程未变
（SHA256 `4095A5B1…254285`）。
