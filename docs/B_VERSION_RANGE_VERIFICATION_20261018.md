# 版本区间 37 条：cpeMatch 对照表（2026-10-18）

由 `tools/verify_version_ranges.py` 生成。输入是
`evaluation/b_relation_candidates_20261010.json` 里 `dimension=version_range`
且 `range=unknown` 的 37 条。数据源：优先本地 `data/snapshots/nvd` 的 cpeMatch；
本地没有的用 `tools/fetch_nvd_cpe.py` 按 CVE 重采（结果并入同一个索引），
重采后 `indexed_cves` 从 12890 条涨到 12918 条。

汇总：37 条里 **19 条能从 cpeMatch 补出区间**，**18 条继续 unknown**（原因逐行写在“缺失项”列）。

unknown 的原因分布：cpeMatch 的 product 与 package 对不上（9 条）；cpeMatch 只有 `*`，没有版本边界（8 条）；本地 NVD 快照里没有该 CVE 的 cpeMatch（1 条）。

| 关系 ID | CVE | package | 原 source_id | 补出的区间 | 状态 | 缺失项 / 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| BREL-VE-0001 | CVE-2026-41106 | Microsoft 365 Copilot | msrc:965ac81937 | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0002 | CVE-2026-41109 | Visual Studio Code | msrc:be7311139e | < 1.119.1 | resolved | cpeMatch < 1.119.1 |
| BREL-VE-0003 | CVE-2026-45499 | Azure Open AI | msrc:fc713234bc | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0004 | CVE-2026-47282 | Visual Studio Code | msrc:f0c1bd7783 | < 1.128.1 | resolved | cpeMatch < 1.128.1 |
| BREL-VE-0005 | CVE-2026-48561 | Microsoft Edge Copilot for Android | msrc:db40986f3a | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0006 | CVE-2026-48561 | Microsoft Edge Copilot for IOS | msrc:a42308afa7 | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0007 | CVE-2026-50510 | GitHub Copilot Plugin for JetBrains IDEs | msrc:d9bec3708c | < 1.13.0-251 | resolved | cpeMatch < 1.13.0-251 |
| BREL-VE-0008 | CVE-2026-50517 | Microsoft 365 Copilot | msrc:5ac70d5d54 | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0009 | CVE-2026-55145 | Microsoft Copilot | msrc:cc090e2b24 | — | unknown | 本地 NVD 快照里没有该 CVE 的 cpeMatch |
| BREL-VE-0010 | CVE-2026-56167 | Azure AI Search | msrc:bc19886686 | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0011 | CVE-2026-58617 | Microsoft 365 Copilot for iOS | msrc:a4811c223f | < 2.111.4 | resolved | cpeMatch < 2.111.4 |
| BREL-VE-0023 | CVE-2026-64849 | MLflow | kev:9dd6ba7cd5 | >= 3.3.0, < 3.15.0 | resolved | cpeMatch >= 3.3.0, < 3.15.0 |
| BREL-VE-0024 | CVE-2025-62593 | Ray | kev:a820ca6fd8 | < 2.52.0 | resolved | cpeMatch < 2.52.0 |
| BREL-VE-0025 | CVE-2026-9198 | Langflow | kev:60fb54585b | >= 1.0.0, < 1.10.1 | resolved | cpeMatch >= 1.0.0, < 1.10.1 |
| BREL-VE-0026 | CVE-2026-0770 | Langflow | kev:e2836e1985 | <= 1.7.3 | resolved | cpeMatch <= 1.7.3 |
| BREL-VE-0027 | CVE-2026-55255 | Langflow | kev:17bfdcf2bb | < 1.9.1 | resolved | cpeMatch < 1.9.1 |
| BREL-VE-0028 | CVE-2025-34291 | Langflow | kev:0238e5afaa | <= 1.6.9 | resolved | cpeMatch <= 1.6.9 |
| BREL-VE-0029 | CVE-2026-33017 | Langflow | kev:cc774f968c | < 1.8.2 | resolved | cpeMatch < 1.8.2 |
| BREL-VE-0030 | CVE-2025-68613 | n8n | kev:bcf2511640 | >= 0.211.0, < 1.120.4 | resolved | cpeMatch >= 0.211.0, < 1.120.4 |
| BREL-VE-0033 | CVE-2025-6558 | Chromium | kev:e46fde0723 | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0034 | CVE-2025-3248 | Langflow | kev:1eacce3542 | < 1.3.0 | resolved | cpeMatch < 1.3.0 |
| BREL-VE-0035 | CVE-2024-4610 | Mali GPU Kernel Driver | kev:c293276891 | >= r34p0, < r41p0 | resolved | cpeMatch >= r34p0, < r41p0 |
| BREL-VE-0036 | CVE-2024-29988 | SmartScreen Prompt | kev:88cb839535 | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0037 | CVE-2023-4211 | Mali GPU Kernel Driver | kev:dc65c96f55 | >= r0p0, < r43p0; >= r12p0, <= r32p0; >= r19p0, < r43p0; >= r41p0, < r43p0 | resolved | cpeMatch >= r0p0, < r43p0 |
| BREL-VE-0038 | CVE-2021-29256 | Mali Graphics Processing Unit (GPU) | kev:f041cb213d | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0039 | CVE-2021-27876 | Backup Exec Agent | kev:cd73f65cd7 | < 21.2 | resolved | cpeMatch < 21.2 |
| BREL-VE-0040 | CVE-2021-27877 | Backup Exec Agent | kev:71ac15a41b | < 21.2 | resolved | cpeMatch < 21.2 |
| BREL-VE-0041 | CVE-2021-27878 | Backup Exec Agent | kev:e2e8e74de1 | < 21.2 | resolved | cpeMatch < 21.2 |
| BREL-VE-0042 | CVE-2023-26083 | Mali Graphics Processing Unit (GPU) | kev:61e498deab | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0043 | CVE-2022-22706 | Mali Graphics Processing Unit (GPU) | kev:b644099a5f | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0044 | CVE-2022-38181 | Mali Graphics Processing Unit (GPU) | kev:c4b140217d | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0045 | CVE-2022-4135 | Chromium GPU | kev:ae99c22581 | < 107.0.5304.150 | resolved | cpeMatch < 107.0.5304.150 |
| BREL-VE-0046 | CVE-2014-6332 | Windows | kev:6e45befc4a | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0047 | CVE-2014-4114 | Windows | kev:eaf4f137b1 | — | unknown | cpeMatch 只有 `*`，没有版本边界 |
| BREL-VE-0048 | CVE-2020-10987 | AC1900 Router AC15 Model | kev:6058689232 | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0049 | CVE-2021-28663 | Mali Graphics Processing Unit (GPU) | kev:e970a840a0 | — | unknown | cpeMatch 的 product 与 package 对不上 |
| BREL-VE-0050 | CVE-2021-28664 | Mali Graphics Processing Unit (GPU) | kev:64634e014d | — | unknown | cpeMatch 的 product 与 package 对不上 |

## 边界

- 只在 cpeMatch 的 product 与候选 package 明确对得上时才采用，宁可 unknown 不硬套；
  目前 9 条卡在这里，都是“同一产品族但名字不同”的情况：`Chromium` 对 `chrome`、
  `SmartScreen Prompt` 对 `windows_10_*`、`Mali Graphics Processing Unit (GPU)` 对
  `bifrost/midgard/valhall_gpu_kernel_driver`、`AC1900 Router AC15 Model` 对 `ac15`。
  要推进它们需要人工确认资产具体型号/代次，本轮不代判；
- 只有 `*`、没有 `versionEndExcluding/Including` 的条目按任务书继续 unknown，
  没有拿别的来源去猜（8 条，主要是 Microsoft 商店类产品）；
- `CVE-2026-55145` 重采时 NVD 断连失败，仍是 unknown；重跑 `fetch_nvd_cpe.py` 会自动只补这一条；
- 原 `source_id` 全部原样保留，本表只补 `range` 与证据位置；
- 没有改动 `evaluation/` 下的冻结产物，也没有写回事件库。

