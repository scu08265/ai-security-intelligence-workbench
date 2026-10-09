# 关系评测 CVSS 漏检复核与重跑结论

B 项 2026-10-04 金标准中 5 条 `cvss` 漏检（FN）的根因是采集链路只把 NVD 的 Exploit 引用
回填进 `poc[]`、丢弃了 CVSS `metrics`（CISA KEV 采集的事件 `cvss[]` 为空）。修复
commit `6d15d31` 后 `tools/backfill_nvd_poc.py` 同时合并 `cvss`。本批次在真实库副本上按
CVE 定向拉取 3 个 CVE 的 NVD CVE API 2.0 原始响应（SHA256 入清单、可逐字节回读），
回填后 4 个事件新获得 CVSS；重跑候选集后四维候选由 121 增到 127（`cvss` 22 → 28）。
旧 5 个合成 id 与新 5 条候选（`BREL-CV-0021..0025`）已用
`tools/verify_b_relation_cvss_recheck.py` 在主体、关系类型、对象、证据四项上逐条核验
一一对应（5/5，每条 11 项检查），映射写进 gold 的 `resolved_former_ids`。这 5 条关系与
金标准期望向量逐字符比对全部命中，已由人工核验、置为 `human_verified` 并署名
（`人工复核-用户确认` / `2026-10-09`）；其余 121 条标注按关系内容迁移，0 条被改写。

评分：页面口径（gold = 用同一协议重跑出的 `evaluation/b_relation_gold_20261006.json`）
TP 52 / FP 0 / FN 0，Precision 1.0、Recall 1.0、F1 1.0，`cvss` 维度 TP 10 → 15、FN 5 → 0。
对照口径（gold = 10-04 冻结 gold）为 TP 52 / FP 0 / FN 5、Precision 1.0、Recall 91.23%、
F1 95.41%；10-04 基线本身是 TP 47 / FN 5、Recall 90.38%、F1 94.95%，即 TP 增加 5、
Recall 上升 0.85pp。两份评分只差 gold：冻结 gold 用 5 个合成 id（`BREL-GOLD-FN-CV-0001..0005`）
记录"应抽取"，而修复后系统抽出的这 5 条关系是新 id，评分器按 `relation_id` 比对
（`missing_ids = expected_ids − 已验证 positive 的 id`），旧 id 无从匹配才仍计为 FN——
这是表示层未收敛，数据侧漏检已经真实收敛。

必须如实说明：页面口径的 100% 只代表当前评测范围——第 2 节那 11 个对象、4 个维度、
抽样穷尽口径，不是全语料召回率；范围内未定项仍单列、范围外不做任何推算。
10-04 的 gold 与两份旧评分产物保持冻结、字节不变（LF 归一化 SHA256 已固定进测试）；
真实库 `D:\ICT\intel-data-b` 全程未变（SHA256 `4095A5B1…254285`）。
