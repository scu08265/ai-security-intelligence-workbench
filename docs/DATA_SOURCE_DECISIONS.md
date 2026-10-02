# POC 与真实资产数据源决定

## 1. POC 状态

当前不接入会执行代码的漏洞利用平台，也不把 CISA KEV 误写成“存在 POC”。

- 权威来源：NVD `references[].tags` 中包含 `Exploit` 的公开引用。
- 存储字段：`event.poc[]`。
- 状态口径：`public_exploit_reference`。
- 解释边界：只说明 NVD 标记了公开利用参考，不代表本系统验证、复现或执行了该利用代码。
- 无记录口径：`event.poc=[]` 只表示当前接入来源没有记录，不能推断 POC 不存在。

该来源是增量接入，覆盖率取决于 NVD 是否维护了 Exploit 标签，因此不会承诺 100% 覆盖。

## 2. 真实资产与策略

真实资产必须由授权调用方提供，系统不从网络扫描或推断企业资产。

- 清单来源：调用方提供的 CycloneDX 1.3-1.7 JSON。
- 真实资产导入：`POST /api/assets/cyclonedx/import`，请求中设置 `is_demo=false`。
- 演示资产：内置样例继续使用 `is_demo=true`，页面会显示“合成”标记。
- 策略来源：随同一请求的 `policies` 对象提供；键可以是资产 ID、组件名或 `bom-ref`。
- 允许字段：`maintenance_window`、`business_importance`、`prohibited_actions`、`owner`、`acceptable_downtime_minutes`。
- 未提供事实：暴露面、业务重要性、运行条件和负责人保持未知，不自动补默认生产值。

示例：

```json
{
  "authorized": true,
  "is_demo": false,
  "bom": {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": []},
  "policies": {
    "vllm": {
      "business_importance": "critical",
      "maintenance_window": {
        "weekday": "Sun", "start": "02:00", "end": "05:00",
        "timezone": "Asia/Shanghai"
      },
      "prohibited_actions": ["restart_service"],
      "owner": "inference-team@example.invalid",
      "acceptable_downtime_minutes": 30
    }
  }
}
```

## 3. 不能由代码自行解决的问题

- POC：如果上游从未打 `Exploit` 标签，本系统不会伪造 POC。
- 真实资产：需要组织提供授权清单。
- 真实策略：需要资产负责人确认维护窗口、禁止动作、负责人和可接受停机时间。
