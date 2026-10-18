# 资产数据源说明（2026-10-15）

**结论先行**：本队**拿不到真实企业资产清单**。没有资产台账、没有漏洞扫描导出、没有 CMDB 导出，
仓库里也不存在任何这类文件。因此资产维度按"**无真实资产数据**"申报，
处置闭环率必须在"合成资产上的流程演示"这一限定下引用。任务书 B1 的两条路里走的是第二条
（书面确认拿不到 + 替代口径）。

## 1. 查过哪些来源，结论是什么

| 候选来源 | 实际情况 | 能否当真实清单 |
| --- | --- | --- |
| CMDB 导出 / 资产台账 / 扫描结果 | 仓库内不存在，也没有任何文件引用过这类来源 | 不能 |
| `artifacts/b_eval/asset_inventory_probe_20261002.json` | **唯一非合成来源**：7 条（fastapi / uvicorn / httpx / packaging / pypdf / starlette / pydantic），`is_demo=false`、`authorized=true`，来源是**本仓库 `.venv` 的 `pip list`**，可复现 | 真实但**非生产**，且缺两个必填维度（见第 2 节） |
| `examples/asset_simulation/vllm-lab/` + `artifacts/sbom/vllm-lab.cdx.json`（3 条） | 目录名即 `asset_simulation`，是**模拟实验室**，不是台账 | 不能 |
| `config/assets.example.json`（`synthetic=true`） | 合成示例，条目 `is_demo=true` | 不能 |
| `artifacts/b_eval/asset_dimension_synthetic_20261002.json`（6 条） | 合成资产，`is_demo=true` | 不能 |
| 演示机 `data/intel.sqlite` 的 8 条资产 | 全部 `is_demo=true`（任务书 2026-10-15 记录） | 不能 |

## 2. 那份"真实但非生产"的清单缺什么

`asset_inventory_probe_20261002.json` 每条只有：

    {asset_id, component, version, is_demo: false, authorized: true, batch_id}

任务书要的五项里，它**缺两项**，而且这两项不能凭常识补：

| 项 | 有没有 | 说明 |
| --- | --- | --- |
| 组件 | 有 | `component` |
| 版本 | 有 | `version`，来自 `pip list` |
| 授权状态 | 有 | `authorized: true` |
| **暴露面** | **没有** | 无来源。只在 `config/asset_policies.example.json` 里以**示例**形式出现 |
| **业务重要性** | **没有** | 同上 |

`config/asset_policies.example.json` 是 `.example` 文件；把它当真实策略填进去，
等于用示例数据冒充资产属性——**本文件明确不做这件事**。

## 3. 替代口径（报告与答辩怎么写）

1. **资产维度写"无真实数据"**，不写 0、也不写"0%"。
   交付语料 `D:\ICT\intel-data-b` 的 `assets` / `assessments` 两张表本身就没有记录；
   演示库的 8 条全是合成资产。判定原则与 `docs/B_DIMENSION_SCOPE_POC_ASSET.md` 一致。
2. **处置闭环率必须带限定语**：现有分母被合成资产主导
   （53 条高优先级里 37 条落在"演示资产：推理服务 C（合成，配置未知）"），
   因此这组数字是**流程覆盖率与流程可用性的演示**，不是生产修复率。
   措辞口径见 `docs/DISPOSITION_CLOSURE.md` §4.4。
3. **演示资产上的 `verified` 只证明复测链路可用**，不证明任何生产系统被修复。
4. 若要展示"通道可用"，用第 2 节那份 7 条真实依赖清单，
   并把暴露面 / 业务重要性标为**未提供**，不臆造。

## 4. 如果要接真实来源，需要什么

任何一条都足以把资产维度从"无数据"变成"有数据"：

* 资产台账 / CMDB 导出（CSV 或 JSON，含组件、版本、暴露面、业务重要性、授权状态）；
* 一次漏洞扫描结果或 SBOM 导出（CycloneDX 或 SPDX，含组件与版本）；
* 任何一个真实部署环境的依赖清单（等价于第 2 节那份，但来自生产环境而非开发机）。

导入方式现成，不需要改代码：

    curl.exe -X POST http://127.0.0.1:8000/api/assets/cyclonedx/import -H "Content-Type: application/json" --data-binary @<真实清单.json>

**注意**：`is_demo` 必须为 `false`，否则又变成合成资产；并且**不得**把示例策略文件
（`config/asset_policies.example.json`）当作真实业务重要性来源。

## 5. 队列构成变化对照（模板）

任务书要求"用真实资产重跑研判后，给出 disposition 队列构成的变化对照"。
这一步**必须在有数据的机器上执行**（本机两个库都是空桩，`assets = 0`）。

    # 1) 登记前的读数
    curl.exe -s http://127.0.0.1:8000/api/dispositions/metrics

    # 2) 导入真实资产（is_demo=false）后重跑研判
    curl.exe -s -X POST http://127.0.0.1:8000/api/assets/cyclonedx/import -H "Content-Type: application/json" --data-binary @<真实清单.json>

    # 3) 登记后的读数
    curl.exe -s http://127.0.0.1:8000/api/dispositions/metrics

把两次读数填进下表即可作为证据（字段名与接口一致）：

| 字段 | 导入前 | 导入后 | 变化原因 |
| --- | ---: | ---: | --- |
| `high_priority_total` | | | |
| `high_priority_registered` | | | |
| `high_priority_unopened` | | | |
| `closure_rate` | | | |
| `registered_closure_rate` | | | |
| `status_breakdown` 各分项 | | | |

**没有真实清单时，本表如实留空**——留空是"没有这一步"，不是"结果是 0"。

## 6. 一句话交接

资产维度缺的是**数据**，不是代码：导入通道、研判、处置闭环链路都已就绪且有测试；
缺的是一份来源可追的真实资产清单。在拿到它之前，页面上的"资产关联 / POC 状态"
不得被当作真实数据引用。