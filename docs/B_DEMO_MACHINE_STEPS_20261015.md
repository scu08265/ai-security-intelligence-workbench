# 演示机上的两步补做（2026-10-15，B 任务）

**为什么需要这份清单**：本轮 B1 与 B3 各有一半成果依赖**有数据的机器**。
开发机上两个库都是空桩（`assets = 0`、`high_priority_total = 0`），
因此本分支提交的是**结构与链路**；下面两步在有数据的机器上跑完，任务书的验收才算完整。
两步都不动冻结产物。

## 第 1 步：处置闭环的字段级对照（B3 验收）

    cd <仓库根>
    .\.venv\Scripts\python.exe tools\check_b_scorecard_consistency.py --out artifacts\b_eval\scorecard_consistency_20261015.json

**必须显式给 `--out`**：脚本默认输出仍是 10-02 那份冻结文件，不给参数会把它覆盖掉。

期望结果：最后一行 `对照字段数: N | 不一致: 0`，且 disposition 段有 **14 个字段**，
包含页面处置闭环卡片实际读取的三个：`closure_rate`、`registered_closure_rate`、
`high_priority_unopened`。

## 第 2 步：队列构成对照（B1 验收，仅当拿到真实资产清单）

**拿不到真实清单就跳过这一步**，并在报告里按 `docs/B_ASSET_DATA_SOURCE.md` §3 的替代口径写
"资产维度无真实数据"，**不要留 0、也不要编数**。

    # 1) 导入前的读数
    curl.exe -s http://127.0.0.1:8000/api/dispositions/metrics

    # 2) 导入真实清单（is_demo 必须为 false）
    curl.exe -s -X POST http://127.0.0.1:8000/api/assets/cyclonedx/import -H "Content-Type: application/json" --data-binary @<真实清单.json>

    # 3) 导入后的读数
    curl.exe -s http://127.0.0.1:8000/api/dispositions/metrics

把两次读数填进 `docs/B_ASSET_DATA_SOURCE.md` §5 的六行表格即可。没有真实清单时该表如实留空。

## 贴回格式

| 步骤 | 贴什么 |
| --- | --- |
| 第 1 步 | 脚本最后一行的 `对照字段数 / 不一致`；若有 `MISMATCH` 行，原样贴出 |
| 第 2 步 | 导入前后的六字段对照表；没有清单就写"未导入，按替代口径申报" |

## 口径提醒（四个坑）

1. **别覆盖冻结产物**：`artifacts/b_eval/scorecard_consistency_20261002.json` 是 10-02 的对照，
   第 1 步务必带 `--out artifacts/b_eval/scorecard_consistency_20261015.json`。
2. **别把"接受风险"当风险消除**：`accepted` 会进分子、抬高闭环率，但只是"决定不修"，
   `assessments.status=affected` 事实不变。
3. **别用 `.example` 策略文件**（`config/asset_policies.example.json`）当真实业务重要性来源。
4. **引用闭环率永远带分母**：全队列 `closure_rate` 与已登记处置内 `registered_closure_rate`
   回答的是两个不同问题，不可互换。

## 相关文档

* 口径：`docs/DISPOSITION_CLOSURE.md` §4（含与接口 `limitations` 逐字一致的四条限定）
* 资产数据源与替代口径：`docs/B_ASSET_DATA_SOURCE.md`
* 数字登记：`docs/B_REPORT_NUMBER_AUDIT.md` §8
* 核对脚本：`tools/check_b_scorecard_consistency.py`（disposition 段）