# 交 A 定的口径清单（2026-10-15）

今天我先修掉了两个**缺陷**（不是口径问题），都已推送：

- `966e2b5` 系统健康面板自相矛盾：自愈那行统计的是"全部历史降级记录"，和同一份响应里的
  `active_degradations`（以及页脚）结论相反；告警那行把 info 级"自愈恢复成功"也算成需关注。
- `ff4e9ad` 冷却到期判断原来拿 ISO 字符串直接比大小；降级理由原来写"连续 N 次采集未成功"，
  但触发规则其实把 `partial` 也算进去了。

下面这些是**语义决策**，改了会影响自愈行为和对外口径，我不单方面动。每条给出：现象 → 证据 →
选项 → 后果 → 我的建议 → 验收方式。请逐条给出选择。

---

## 前置事实（后面都引用这些）

| 事实 | 值 | 位置 |
| --- | --- | --- |
| 降级阈值 / 冷却 / 重试预算 | 3 次 / 6 小时 / 1 次 | `app/self_healing.py` |
| `CollectorOutcome.ok` | `status in {"ok", "partial"}` | `app/collectors/__init__.py:57` |
| `consecutive_failures()` 认证 | 只有 `status == "ok"` 才算成功 | `app/self_healing.py` |
| `RETRYABLE_SOURCE_STATUSES` | `{"stale", "failed"}`（**不含 partial**） | `app/self_healing.py` |
| 无人值守采集来源集 | 19 个，ghsa 在内 | `sources.recommended_sources()` |
| ghsa 备用源 | 无（`backup_sources=()`），故动作为 `reduce_frequency` | `app/sources.py:89` |

---

## 决策 1（最重要）：`partial` 算不算"连续失败"？

**现象**：ghsa 现在是 `status=partial`、`last_success=2026-10-15T12:18:55Z`、
`events_count=104`、`consecutive_failures=33`。今天 `streak > 0` 的来源只有它一个。

**证据（三条路径合起来才是完整故事）**：

1. ghsa 采集器**设计上**就是达到抓取预算报 `partial`，不静默截断
   （`app/collectors/vuln.py:5-6`，`:120 / :210 / :268`）——这是正常行为，不是故障。
2. `partial` 不在 `RETRYABLE_SOURCE_STATUSES` 里，所以**自愈永远不会为它重试**。
3. 但 `run_self_healing` 的降级循环遍历的是"所有有状态行的来源"，而不只是本次候选
   （`app/self_healing.py`，`streaks` 取自 `set(fresh_states) | set(candidates)`）。
   于是**只要别处出现 failed/stale 触发一次自愈，ghsa 就会被顺带重新写入 6 小时冷却**；
   随后 `apply_degradation_policy` 按 `reduce_frequency` 把它从该次无人值守采集里移出
   （`substituted_with=[]`，因为它没有备用源）。

   实际观察：最近一条降级记录 `degraded_at=2026-10-15T02:43:36Z`、
   `expires_at=2026-10-15T08:43:36Z`（已过期，当前无生效中的降级）；08:43 之后没有再触发自愈，
   所以 ghsa 现在仍在正常采集。**下次别处一失败，它就会被再次降频**——不连续、也不可预期。

**选项**：

- **A1 排除**：`consecutive_failures` 把 `ok | partial` 都当成功，streak 只统计真正 failed（stale 见决策 2）。
  理由：撞预算是设计行为。后果：一个真·长期半坏的来源也不会被降频。
- **A2 分类阈值**：`partial` 单独计数，只有"连续 partial 且零事件产出"才算降级；
  有备用源的走备用源。理由：区分"能采到但不全"和"什么都采不到"。后果：多一个阈值要维护。
- **A3 维持现状**：只在文档里写清"partial 计入降级触发是设计决定"，答辩时说明"被降频不等于来源坏了"。
  后果：ghsa 会周期性降频，无人值守时段的实际产出来源数会少于 15。

**我的建议**：A2；来不及就 A1（改动小、可复测），A2 记 TODO。
理由是 ghsa 属于 15 个实际产出来源，而它的 partial 是设计行为——用 partial 触发降频，
会让"无人值守时段到底有几个来源在产出"这个数字自己也说不清。

**验收**：给一张表，按新口径列出今天哪些来源会/不会被降级（应只有 ghsa 受影响），
并说明对"无人值守采集来源数"的影响；`pytest tests/test_self_healing.py` 覆盖新口径。

---

## 决策 2：`stale` 的语义要跟决策 1 一起定

`stale` 会被送去重试（在 `RETRYABLE_SOURCE_STATUSES` 里），同时又被算作"非成功"
（不计入 streak 的 break 条件）。ghsa 的历史 run 里出现过 `stale`
（`ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING]`、`ConnectTimeout: handshake timed out`）。

**要定**：`stale` 与 `failed` 是否同等计入 streak？在口径文档里写清 stale 的定义
（"上游连不上、但历史数据仍在"）。**建议**：与 `failed` 同计，但要在文档里点明它与 `partial` 的区别。

**验收**：口径文档里 stale / failed / partial / skipped 四个取值各有一句定义与是否计入降级。

---

## 决策 3：同一次 partial 运行，`last_success` 说"成功"、streak 说"不成功"

**证据**：ghsa 的 `source_state` 同一行里 `status=partial` 且 `last_success=2026-10-15T12:18:55Z`
——这个 `last_success` 就是那次 partial 运行戳上去的（`app/agents.py:496` 在 `outcome.ok` 为真时戳，
而 `partial ∈ ok`）。而健康面板"采集与监测"那行写的是"最近一次成功 `max(last_success)`"，
于是页面上的"成功"可能来自一次 partial。

**要定**：`last_success` 是否只由完全成功（`status == "ok"`）刷新？

**我的建议**：保留现状（partial 也刷新），否则一个长期 partial 的来源会永远显示"从未成功"，
更误导；但请同时确认页面/答辩时怎么解释"最近一次成功"，必要时把文案改成
"最近一次有产出的运行"。

**验收**：给出选定语义 + 对应的页面文案（若改文案，要同步 `docs/` 与截图）。

---

## 决策 4（小、偏机械）：降级记录里的 `failure_class` 恒为 `unknown`

**证据**：ghsa 记录 `failure_class="unknown"`。原因在 `degradation_for()` 里硬编码
`classify_failure("failed", None)` → 文本只有 "failed" → 匹配不到任何关键字 → 恒返回 `unknown`。
可 `classify_failure` 本来支持 `rate_limit / upstream_timeout / authentication / format_change /
connection_reset / upstream_rejected`，而来源状态里就有真实的 `status` 和 `last_error` 可用。

**要定**：把真实 `status` / `last_error` 传进 `degradation_for()` 计算分类，还是干脆删掉这个字段
（避免一个永远是 `unknown` 的字段被当成"已分类"）。

**我的建议**：传真实值计算。

**验收**：新记录里 `failure_class` 与 `last_error` 自洽（例如 ghsa 的连接错误应得到
`connection_reset` 或 `upstream_timeout`），并有测试钉住。

---

## 决策 5（可选）：告警需不需要时间基线

今天已修"info 级恢复通知不再算需关注"。但窗口固定是"最近 20 条"，与时间无关：
一条三天前的 warning 也会让模块一直显示需关注。

**要定**：是否改成时间窗（如最近 24 小时）而非条数；warning 是否要在页面上展开成清单。

**我的建议**：维持条数窗口（数据量小、实现简单），但在答辩口径里写明
"需关注 = 最近 20 条里存在 warning 及以上"。

---

## 交付要求

每条给出：**选定选项 + 一句理由 + 影响面（会变哪些数字/页面）+ 是否有测试覆盖**。
不要为了降低"需关注"数量去改判定标准；口径要能自我解释。
