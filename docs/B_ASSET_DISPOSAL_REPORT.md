# B 任务四：策略感知资产处置建议 · 实现与验收报告

**范围**：在**不改动共享业务代码与数据库 schema** 的前提下，实现"安全情报 + 资产事实 + 运维策略 →
有证据依据、遵守约束、可解释、可排序的处置建议"，并交付测试与演示证据。

---

## 一、现状检查结论（先分类，再动手）

| 类别 | 内容 | 处置 |
| --- | --- | --- |
| 已实现且可用 | `app.intelligence.assess_asset`（版本区间/条件判定 + 证据 ID + 状态）、`app.intelligence.enrich_event`（证据维度、缺口、POC、在野利用）、`app.intelligence._priority`（粗粒度优先级） | 直接复用为事实层 |
| 已实现但缺测试 | 上述事实层在"资产×策略"场景下没有测试 | 本轮通过新模块的测试间接覆盖（断言其在策略场景下的输出） |
| 未实现 | 策略输入与校验、动作目录、可解释优先级、运维约束检查、建议输出、演示 | 本轮新实现（独立模块，不碰 `app/`） |

实测数据现状：`assets` 表 **0 条**、`assessments` **0 条**、`events` **93 条**；
93 条事件中只有 1 条带 `severity=high`，其余严重性靠 `cvss[].score` 推导；
**没有任何事件同时具备"在野利用关系"与"具体受影响区间"**（KEV 事件区间均为 `unknown`）。
这两点直接决定了演示必须使用**合成资产**（明确标记）与**真实事件**的组合。

## 二、实现概览与文件清单

| 文件 | 作用 |
| --- | --- |
| `tools/asset_disposal_advisor.py` | 核心模块：策略解析/校验、事实关联、优先级、约束检查、建议输出、演示运行（CLI） |
| `config/asset_policies.example.json` | 策略示例（六个必需字段；合成数据，`synthetic: true`） |
| `config/assets.example.json` | 资产示例（字段与 `AssetRequest` 对齐；合成数据） |
| `artifacts/b_eval/asset_disposal_demo.json` | 演示运行结果（3 个案例 + 逐资产/逐事件建议） |
| `tests/test_b_asset_disposal_advisor.py` | 16 条功能测试（覆盖验收要求的 12 个场景） |
| 本报告 | 说明、验收与遗留问题 |

**未修改**：`app/` 任何文件、数据库 schema、采集器、问答主链路；未新增数据库表。

## 三、策略输入

### 3.1 六字段与校验规则

| 字段 | 类型 | 校验 | 缺失时 |
| --- | --- | --- | --- |
| `asset_id` | 字符串 | 必填、同一文件内唯一 | 报错 `PolicyError` |
| `maintenance_window` | 对象或 `null` | `weekday ∈ Mon..Sun`；`start`/`end` 为 `HH:MM` 且 `start < end`；`timezone` 必填（显式给出） | 允许 `null`；破坏性动作改判"需人工安排维护窗口" |
| `business_importance` | 枚举 | `low / medium / high / critical`，非法值报错 | 默认 `unknown`（优先级分量记 0 并列入 gaps） |
| `prohibited_actions` | 字符串数组 | 必须是字符串数组；未登记动作保留但给出告警 | 默认空数组 |
| `owner` | 字符串或 `null` | 类型校验 | `null` → 输出"负责人未知，需人工指派" |
| `acceptable_downtime_minutes` | 非负整数 | 负数/非整数报错 | 缺省按 **0 分钟**（不假设可停机） |

### 3.2 无策略资产的默认规则（保守）

`default_policy()`：**可接受停机 0 分钟**、**破坏性动作（补丁/重启/降低暴露面）全部列入禁止**、
负责人 `null`、`explicit=false`，并在输出中标注"默认规则不代表资产真的不能停机，
只代表系统不假设它可以停机"。

### 3.3 存储位置与修改方法

- 位置：`config/asset_policies.example.json`（示例模板）与 `config/assets.example.json`（资产模板）。
- 格式：JSON；顶层可为数组，或 `{"synthetic": bool, "policies": [...]}`。
- 修改方法：复制示例 → 改 `asset_id` 与六字段 → 用 `--policies` / `--assets` 指向自己的文件。
- 示例片段：

```json
{"asset_id": "asset-demo-vllm-prod",
 "maintenance_window": {"weekday": "Sun", "start": "02:00", "end": "05:00",
                        "timezone": "Asia/Shanghai"},
 "business_importance": "high", "prohibited_actions": [],
 "owner": "team-inference@example.invalid", "acceptable_downtime_minutes": 30}
```

## 四、处置流程与证据分层

流程：**事实 → 资产关联 → 风险与约束分析 → 排序 → 建议与证据**。

关联逻辑**复用** `app.intelligence.assess_asset`，因此天然区分三种情况并在输出中显式标注：

| 分层 | 触发条件 | 输出标记 |
| --- | --- | --- |
| `confirmed` | 资产版本命中事件 `affected[].range`，且条件项满足 | `link_status = affected` |
| `inferred` | 组件匹配但版本未知 / 区间不可解析 / 条件未知 | `link_status = needs_confirmation` |
| 缺失 | 组件不匹配或事件缺区间 | 不作为该资产对象（组件不匹配直接跳过），或在 gaps 中列出 |

**不允许**仅凭组件名相似就认定资产受影响：组件不匹配时直接不进 `findings`（测试覆盖）。

## 五、优先级排序（可解释、缺数据不猜）

分值 = 分量之和（0–100），权重写在模块常量 `PRIORITY_WEIGHTS` 中：

| 分量 | 取值与得分 |
| --- | --- |
| severity | critical 40 / high 30 / medium 15 / low 5 / unknown 0（严重性优先取 `severity`，缺失时由 `cvss[].score` 推导） |
| exploitation | `known_exploited`（CISA KEV 关系）25 / `poc_recorded` 15 / `none_recorded` 0 |
| business_importance | critical 20 / high 15 / medium 8 / low 3 / unknown 0 |
| exposure | public 10 / internal 5 / unknown 0 |
| link_confidence | affected 5 / needs_confirmation 0 |

等级：≥70 `critical`、≥50 `high`、≥30 `medium`，否则 `low`。
**关键降级规则**：只要 `link_status ≠ affected`，就不给出精确分值，`level = 待核实`、
`score = null`、`score_is_provisional = true`，并保留参考分量与 gaps——避免用推断风险冒充确定风险。
缺失输入一律记 0 分并写入 `gaps`（如"缺少严重性/CVSS""未收录 POC/在野利用"）。

## 六、运维约束检查（独立环节，可测试）

| 约束 | 行为 |
| --- | --- |
| 禁止动作 | 命中 `prohibited_actions` 的动作进入 `blocked_actions`，并生成冲突说明"事实层建议它，但策略禁止，需要人工选择替代方案" |
| 维护窗口 | 破坏性动作输出 `scheduling`：有窗口 → `inside_declared_window_only` + `allowed_from/until` + 时区；无窗口 → `needs_window`（需人工安排）；非破坏性动作 → `not_required` |
| 可接受停机 | 预计停机 > 可接受停机时打 `constraint_warning`（"不得作为无条件推荐"）并列入冲突 |
| 人工批准 | 所有破坏性动作 `requires_approval = true`；无策略资产额外标注"默认禁止破坏性操作" |
| 冲突 | 任何被拦下/超限/信息缺失都会把条目 `needs_human_review = true`，并在 `conflicts` 写明原因 |

系统**只输出建议**，不执行扫描、隔离、升级、关机；输出中固定带该限制说明。

## 七、测试覆盖与实测结果

`tests/test_b_asset_disposal_advisor.py` → **16 passed**（合成资产 + 合成事件验证逻辑；
演示产物另测）。覆盖验收要求的 12 个场景：

| # | 场景 | 对应测试 | 结果 |
| --- | --- | --- | --- |
| 1 | 高业务重要性 vs 普通资产 | `test_business_importance_changes_priority` | 通过（20 分 vs 3 分） |
| 2 | 同漏洞不同资产的排序差异 | `test_same_event_different_assets_rank_by_facts_and_policy` | 通过（分值不同、证据相同） |
| 3 | 维护窗口内/外 | `test_maintenance_window_and_missing_window_change_scheduling` | 通过（`inside_declared_window_only` vs `needs_window`） |
| 4 | 禁止动作阻止推荐 | `test_prohibited_action_blocks_recommendation_and_explains_conflict` | 通过（进入 `blocked_actions` + 冲突） |
| 5 | 可接受停机影响方案 | `test_acceptable_downtime_limits_unconditional_recommendation` | 通过（15 > 5 触发告警） |
| 6 | 负责人缺失 | `test_missing_owner_and_missing_policy_are_marked_not_guessed` | 通过（owner=null + 需人工） |
| 7 | 修复版本缺失 | `test_missing_fixed_version_switches_to_verification_and_monitoring` | 通过（改判核实/监测） |
| 8 | CVSS/POC 缺失 | `test_missing_cvss_and_poc_are_recorded_as_gaps_not_scores` | 通过（分量 0 + gaps） |
| 9 | 证据不足不得认定受影响 | `test_unknown_version_is_needs_confirmation_without_score`、`test_component_mismatch_is_not_attributed_to_the_asset` | 通过（待核实 / 直接排除） |
| 10 | 策略冲突需人工确认 | `test_conflicting_policy_requires_human_review_with_reason` | 通过 |
| 11 | 证据与资产标识可追溯 | `test_evidence_ids_and_asset_identity_are_traceable` | 通过（每条建议都绑定证据） |
| 12 | 空输入/非法字段/无匹配/无证据 | `test_invalid_policy_fields_are_rejected`、`test_empty_inputs_degrade_gracefully`、`test_policy_file_duplicate_ids_are_rejected` | 通过（报错或结构化空结果） |

## 八、三个演示案例（`artifacts/b_eval/asset_disposal_demo.json`，合成资产 + 真实事件）

运行：`tools/asset_disposal_advisor.py --demo --out artifacts/b_eval/asset_disposal_demo.json`
（实测：6 个合成资产、7 条建议、4 条需人工复核）

**案例 A · 高优先级风险处置**（`asset-demo-smolagents-prod`，合成资产 smolagents 1.20.0）

| 项 | 实测值 |
| --- | --- |
| 关联事件 | `CVE-2025-9959`（真实事件） |
| 关联结论 | `affected`（1.20.0 命中 MITRE 记录的 `>= 0, < 1.21.0`） |
| 优先级 | `high`，分值 **65**（severity 30 + business 20 + exposure 10 + link 5） |
| 建议动作 | `verify_version`、`enhanced_monitoring`、`further_verification` |
| 未给补丁的原因 | 事件未提供修复版本（`fixed_version=null`）→ 动作目录不会凭空推荐升级 |
| 证据 ID | `mitre:*`、`nvd:*`（来自事件 sources 与 CVSS 记录），逐条绑定在建议上 |

**案例 B · 业务约束下的处置调整**（同一漏洞 `PYSEC-2026-4000`、同一版本 0.29.0）

| 资产 | 业务重要性 | 可接受停机 | 维护窗口 | 优先级 | 关键差异 |
| --- | --- | ---: | --- | --- | --- |
| `asset-demo-vllm-prod` | high | 30 min | Sun 02:00–05:00 | low（25） | 补丁 15 min 在可接受范围内，窗口为周日凌晨 |
| `asset-demo-vllm-lab` | low | 240 min | Wed 09:00–18:00 | low（13） | 同动作、窗口与停机余量完全不同 |
| `asset-demo-vllm-edge` | critical | **5 min** | Mon 01:00–02:00 | medium（35） | **15 min > 5 min → 触发"不得作为无条件推荐"冲突，需人工确认** |

**案例 C · 证据不足与策略冲突**

| 资产 | 现象 | 输出 |
| --- | --- | --- |
| `asset-demo-copilot-prod`（版本 unknown） | 组件匹配但版本未知 | `link_status=needs_confirmation`、`level=待核实`、`score=null`、动作仅 `further_verification`、需人工复核 |
| `asset-demo-openwebui`（禁止补丁、无窗口、停机 0、无负责人） | 事实层建议补丁但策略禁止 | `apply_patch` 进入 `blocked_actions`（原因=策略禁止）+ 冲突说明 + 负责人未知 + 需人工复核 |

## 九、遗留问题

**必须修复项（依赖数据或共享模块，需单独授权）**

1. 修复版本与严重性/利用证据在真实数据中不重叠：93 条事件里，带具体区间的条目基本没有
   `severity`，带 KEV 关系的条目区间均为 `unknown` → 演示无法同时展示"确认受影响 + 在野利用 + 补丁"。
   建议后续补齐 KEV 事件的版本区间或为 OSV 条目补充数值分数。
2. 资产数据为空（`assets` 表 0 条）：真实资产接入前，系统只能对显式提供的资产文件工作。
3. `policy` 若要进数据库/API，需改共享 `AssetRequest` 与 `storage`，**需与 A 任务负责人协调**（本轮未做）。

**可选改进项**

1. 动作目录中的停机估算（补丁 15 min、重启 5 min 等）是**配置值**，建议按实际发布流程校准。
2. 优先级权重目前是固定常量，可按组织风险偏好外置为配置文件。
3. 可增加"当前时间是否在维护窗口内"的判断（现在只输出允许窗口，不判断当前时刻）。

**依赖数据的问题**

1. 条件触发类漏洞（`conditions`）需要资产提供配置项，示例资产未提供 → 相关事件会落在 `needs_confirmation`。
2. POC 状态来自事件 `poc[]`（当前 93 条事件均为空）→ exploitation 分量基本为 0，已在 gaps 中说明。

## 十、验收问题速答

| 问题 | 答案 |
| --- | --- |
| 策略输入是否真实可用？ | 可用：六字段解析 + 严格校验 + 保守默认规则；示例见 `config/asset_policies.example.json`（合成） |
| 资产、漏洞、证据能否正确关联？ | 能：复用 `assess_asset` 的版本区间判定；组件不匹配直接排除，版本未知降级为待核实 |
| 优先级是否有可解释依据？ | 有：五分量加权（严重性/利用证据/业务重要性/暴露面/关联置信），缺失记 0 并列出 gaps |
| 禁止动作/维护窗口/停机是否真正影响输出？ | 是：分别产生 `blocked_actions`、`scheduling.needs_window`、`constraint_warning` 与冲突说明（均有测试） |
| 信息不足能否降级？ | 能：`待核实` + `score=null` + `needs_human_review=true`，不编造精确分值 |
| 输出是否可追溯证据？ | 是：每条建议与每条发现均带 `evidence_ids`（如 `osv:`/`msit:`/`nvd:`/`kev:` 前缀） |
| 关键测试是否全部通过？ | 是：16/16 通过（含 12 个验收场景），失败项 0 |
| 三个演示案例能否复现？ | 能：一条命令 `--demo` 生成，产物为 `artifacts/b_eval/asset_disposal_demo.json` |
| 哪些已实现、哪些只是设计？ | 已实现：策略、关联、优先级、约束、建议、演示、测试；仅设计未实施：策略入 DB/API、当前时刻窗口判断、真实资产接入 |
| 是否发生数据库变化？ | 无（只读打开，SHA256 与大小不变） |
| Git 状态？ | 分支 `feat/b-evaluation`，暂存区空，未执行任何 git 写操作（详见最终汇报） |
| B 任务二/三是否保持原状？ | 任务二仍暂停（人工标注 0 填写）；任务三文件与结果未改动、未重跑 |
