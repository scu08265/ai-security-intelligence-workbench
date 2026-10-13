# B 项 POC / 资产维度口径说明（2026-10-12）

**一句话结论**：POC 与资产关联这两个维度缺的是**数据**，不是代码。交付语料
`D:\ICT\intel-data-b\intel.sqlite` 里 `events[].poc[]` 一条没有，`assets` / `assessments`
两张表也没有记录，所以这两个维度**没有可计算的分母**。报告里写"无数据"，不要写 0 ——
"算出来是 0"和"根本没有分母"是两种含义，混用会把口径问题说成能力问题。

这与"还差两个衍生副本"是两件独立的事：衍生副本影响的是 4 条测试能否运行，
这里说的是这两项指标在这份语料里根本没有数据源。

## 1. 实测（2026-10-12，只读查库）

| 项 | 值 |
| --- | --- |
| events / event_aliases | 93 / 15 |
| rag_documents / rag_chunks | 22 / 3639 |
| events 含 `cvss[]` | 22 |
| **events 含 `poc[]`** | **0** |
| **assets / assessments** | **无记录** |

复现方式：以只读方式（`file:…?mode=ro`）打开 `D:\ICT\intel-data-b\intel.sqlite`，
对 `events` / `assets` / `assessments` 直接取行数，并统计事件文档里 `poc[]` / `cvss[]` 非空的条数。
本轮没有写入、没有建副本、没有改动交付语料的字节。

## 2. POC 维度

**数据来源**：`events[].poc[]` 的每一条对应 NVD 记录里 `references[]` 中 `tags` 含 `Exploit`
的引用（来源决策见 `docs/DATA_SOURCE_DECISIONS.md`）；回填工具是 `tools/backfill_nvd_poc.py`，
经 `storage.merge_event_poc()` 合并进事件文档。

**为什么是空的**：采集链路写入事件时不携带 POC，POC 只能靠 NVD 快照回填，而快照必须与本库同源。
`artifacts/b_eval/nvd_poc_backfill_20261002.json` 记录了用既有快照回填的结果：
`events_updated = 0`，144 个事件全部未命中——不是代码没跑通，是快照和库不同源。

**能不能补：能，但要走外部抓取 + 写副本。**
`artifacts/b_eval/nvd_poc_backfill_cve_scope_20261002.json` 是实测证据：按库内 37 个 CVE
逐个拉 `https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=…`，在库副本
`D:\ICT\intel-data-b-poc-20261002` 上回填，得到 `events_updated = 16`、`poc_records = 32`
（逐 CVE 明细见 `artifacts/b_eval/nvd_poc_snapshot_manifest_20261002.json`）。
两个前提：要联网；而且**回填只能写副本**——交付语料已被哈希核验，改它会让指纹和已交付的报告全部失效。

**报告怎么写**：写"POC 维度无数据：93 个事件中 0 个带 POC 字段，采集链路未入库"，
并把"可按库内 37 个 CVE 抓取 NVD 定向回填（实测 16 个事件）"作为已探明的补充路径。
不要写"POC 识别准确率 0%"。

## 3. 资产维度（assets / assessments）

**数据来源**：`assets` 表由 CycloneDX SBOM 导入（`app/cyclonedx_assets.py`，
等价于 `POST /api/assets/cyclonedx/import`）；`assessments` 表记录"事件 × 资产"的处置研判。

**为什么是空的**：交付语料里这两张表都没有记录。现有两条可用通道都不是企业资产源：

* 合成 BOM：`config/assets.example.json`（`synthetic: true`，条目 `is_demo: true`），导入 13 条，
  见 `artifacts/b_eval/asset_dimension_synthetic_20261002.json`；
* 本机依赖清单：把仓库 `.venv` 的 `pip list` 转成 BOM（`is_demo: false`），
  见 `artifacts/b_eval/asset_inventory_probe_20261002.json`——它证明导入通道可用，
  但描述的是这台开发机，不是任何真实资产。

**能不能补：补不上。** 我们没有企业资产清单这一来源，也不应该伪造。可行的只有：
明确标注为合成资产（`asset.synthetic = true`），把该维度的结论限定为
"策略感知处置建议"，而不是"个性化资产推荐"。

**报告怎么写**：写"资产关联维度无数据：交付语料 `assets` / `assessments` 均无记录；
该维度以合成资产演示策略感知处置建议"。不要写 0%。

## 4. 不要混引：评测语料 ≠ 演示机基线库

两个库都有数字，但回答的是不同问题，不能混排在同一张指标表里
（引用规则见 `docs/METRICS_BASELINE.md` 第 3 节）：

| | B 评测语料 | 演示机基线库 |
| --- | --- | --- |
| 路径 | `D:\ICT\intel-data-b\intel.sqlite` | 仓库内 `data/intel.sqlite` |
| events | 93 | 548 |
| assets / assessments | 无记录 | 8 / 190 |
| 用途 | 关系 / 问答 / RAG 评测的分母 | 页面与对外的口径 |

因此"资产维度无数据"这句话**只在评测语料上成立**；演示机基线库确实有 8 条资产、190 条研判。
引用时带上数据集限定语，就不会出现"同一份报告里一处说没有资产、一处说 8 条"的矛盾。

## 5. 可直接引用的两句话

* "POC 维度无数据：评测语料 93 个事件中 0 个带 `poc[]`，原因是采集链路不回填 POC；
  已探明可按库内 37 个 CVE 抓取 NVD 定向回填（实测 16 个事件），本轮未纳入。"
* "资产关联维度无数据：评测语料 `assets` / `assessments` 均无记录，没有真实资产来源；
  该维度以合成资产做策略感知处置演示，不作为个性化推荐指标。"
