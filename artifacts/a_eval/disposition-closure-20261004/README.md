# A 项处置闭环复测证据

本目录由 `tools/run_disposition_evidence.py` 在独立数据库副本上通过正式 API 流程生成。

## 结果

- 高优先级 `affected` 基线：4
- 已复测关闭：3
- 失败复测并保持 `fixed`：1
- 闭环率：0.75
- verified_rate：0.75
- 页面与 API 字段差异：0

## 文件

- `evidence.json`：完整请求、响应、规则结果、指标时间线
- `before-after.json`：处置前后与合成/真实边界
- `page-consistency.json`：metrics、scorecard 和页面绑定字段核对
- `state-machine-rules.csv`：4 条状态机规则逐项实测
- `closure-timeline.csv`：闭环率从 0 到 0.75 的过程

## 声明

选中高优先级条目全部来自合成 `asset-cdx-*` 资产。7 个真实运行时依赖资产已导入并参与研判，
但没有产生高优先级 `affected` 条目。当前结果证明流程和口径正确，不代表生产环境已经执行修复。
