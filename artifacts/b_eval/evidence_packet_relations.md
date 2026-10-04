# 关系证据核验工作包

生成自本地快照与自动核验结果；共 34 条。**标签列一律留空，等待人工填写。**

---

## 一、fixed_version（12 条）

### BREL-FI-0001 · fixed_version

- **主体 / 关系 / 客体**：`PYSEC-2026-4000` / `fixed_by` / `vllm@0.30.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.30.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.30.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.30.0 不落在受影响区间 < 0.30.0；R-FV-SNAPSHOT: 原始快照 包含 '0.30.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.30.0']，候选='0.30.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/08e1baad2cecde5d9a5c797c318722171dc9832e7329304d9d746947f074b934.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.30.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.30.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.30.0 不落在受影响区间 < 0.30.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.30.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.30.0']，候选='0.30.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.30.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0002 · fixed_version

- **主体 / 关系 / 客体**：`PYSEC-2026-3998` / `fixed_by` / `vllm@0.29.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.29.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.29.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.29.0 不落在受影响区间 < 0.29.0；R-FV-SNAPSHOT: 原始快照 包含 '0.29.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.29.0']，候选='0.29.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/b9440e819799ff3b43e23a164d61ffdf6be3e85ba4a69cc1799236d645645462.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.29.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.29.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.29.0 不落在受影响区间 < 0.29.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.29.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.29.0']，候选='0.29.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.29.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0003 · fixed_version

- **主体 / 关系 / 客体**：`PYSEC-2026-3999` / `fixed_by` / `vllm@0.30.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.30.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.30.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.30.0 不落在受影响区间 < 0.30.0；R-FV-SNAPSHOT: 原始快照 包含 '0.30.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.30.0']，候选='0.30.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/c30815fb9f87727ed13e2729ac5f69bdc2bf2e4333466f7c08d79f123407d524.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.30.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.30.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.30.0 不落在受影响区间 < 0.30.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.30.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.30.0']，候选='0.30.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.30.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0004 · fixed_version

- **主体 / 关系 / 客体**：`PYSEC-2026-3997` / `fixed_by` / `vllm@0.28.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.28.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.28.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.28.0 不落在受影响区间 < 0.28.0；R-FV-SNAPSHOT: 原始快照 包含 '0.28.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.28.0']，候选='0.28.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/5f29c77279f71baaaa32e4a071dc6a660e7b7af485d346508b4418c3b8806550.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.28.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.28.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.28.0 不落在受影响区间 < 0.28.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.28.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.28.0']，候选='0.28.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.28.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0005 · fixed_version

- **主体 / 关系 / 客体**：`PYSEC-2026-3996` / `fixed_by` / `vllm@0.30.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.30.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.30.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.30.0 不落在受影响区间 < 0.30.0；R-FV-SNAPSHOT: 原始快照 包含 '0.30.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.30.0']，候选='0.30.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/b478fb82de5d93e18084254420bbfc703a0b6e84ba2c20bab6907f5cbd8cdebb.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.30.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.30.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.30.0 不落在受影响区间 < 0.30.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.30.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.30.0']，候选='0.30.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.30.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0006 · fixed_version

- **主体 / 关系 / 客体**：`GHSA-8pw2-6jv3-mj5j` / `fixed_by` / `vllm@0.28.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.28.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.28.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.28.0 不落在受影响区间 < 0.28.0；R-FV-SNAPSHOT: 原始快照 包含 '0.28.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.28.0']，候选='0.28.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/5ec93b0e68589ed193d2c5bbeb1f7edc0bf869edce96a714ec8c500d02fc1cb3.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.28.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.28.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.28.0 不落在受影响区间 < 0.28.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.28.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.28.0']，候选='0.28.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.28.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0007 · fixed_version

- **主体 / 关系 / 客体**：`GHSA-hcwq-8wjf-3gcr` / `fixed_by` / `vllm@0.24.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.24.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.24.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.24.0 不落在受影响区间 < 0.24.0；R-FV-SNAPSHOT: 原始快照 包含 '0.24.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.24.0']，候选='0.24.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/1f26b5e5797b4057a910378c02a1139671eae131bf4560cf65b9328528ab9646.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.24.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.24.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.24.0 不落在受影响区间 < 0.24.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.24.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.24.0']，候选='0.24.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.24.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0008 · fixed_version

- **主体 / 关系 / 客体**：`PYSEC-2026-3985` / `fixed_by` / `vllm@0.28.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.28.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.28.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.28.0 不落在受影响区间 < 0.28.0；R-FV-SNAPSHOT: 原始快照 包含 '0.28.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.28.0']，候选='0.28.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/a2f3f13da0780b28558d193546127b1ecda72a69c89a1cec62a970930b66d5b7.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.28.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.28.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.28.0 不落在受影响区间 < 0.28.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.28.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.28.0']，候选='0.28.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.28.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0009 · fixed_version

- **主体 / 关系 / 客体**：`GHSA-wvm9-9g5j-623f` / `fixed_by` / `open-webui@0.11.1`
- **候选值**：`{"package": "open-webui", "fixed_version": "0.11.1"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.11.1 可解析为版本；R-FV-CONSISTENCY: fixed=0.11.1 不落在受影响区间 >= 0.8.0, < 0.11.1；R-FV-SNAPSHOT: 原始快照 包含 '0.11.1' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.11.1']，候选='0.11.1'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/579265ef2af27fecd42dde2e00017f2b6aa834e84348ec5d19f2eb2be471355b.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "open-webui", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0.8.0"}, {"fixed": "0.11.1"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.11.1 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.11.1 不落在受影响区间 >= 0.8.0, < 0.11.1`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.11.1' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.11.1']，候选='0.11.1'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.11.1？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0010 · fixed_version

- **主体 / 关系 / 客体**：`GHSA-3g9q-v48f-hh9w` / `fixed_by` / `open-webui@0.11.1`
- **候选值**：`{"package": "open-webui", "fixed_version": "0.11.1"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.11.1 可解析为版本；R-FV-CONSISTENCY: fixed=0.11.1 不落在受影响区间 >= 0.9.0, < 0.11.1；R-FV-SNAPSHOT: 原始快照 包含 '0.11.1' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.11.1']，候选='0.11.1'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/943ad60707eae33503855dc72e69353747fb3ebfa105a9579e2bae6f9ae5dac1.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "open-webui", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0.9.0"}, {"fixed": "0.11.1"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.11.1 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.11.1 不落在受影响区间 >= 0.9.0, < 0.11.1`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.11.1' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.11.1']，候选='0.11.1'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.11.1？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0011 · fixed_version

- **主体 / 关系 / 客体**：`GHSA-v39v-59xw-j98g` / `fixed_by` / `open-webui@0.11.1`
- **候选值**：`{"package": "open-webui", "fixed_version": "0.11.1"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.11.1 可解析为版本；R-FV-CONSISTENCY: fixed=0.11.1 不落在受影响区间 >= 0.9.0, < 0.11.1；R-FV-SNAPSHOT: 原始快照 包含 '0.11.1' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.11.1']，候选='0.11.1'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/7f6b0730c264a3430be3c50a000a1e6ccf8a04e69fba1d3f48c8b01eb616aedf.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "open-webui", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0.9.0"}, {"fixed": "0.11.1"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.11.1 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.11.1 不落在受影响区间 >= 0.9.0, < 0.11.1`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.11.1' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.11.1']，候选='0.11.1'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.11.1？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-FI-0012 · fixed_version

- **主体 / 关系 / 客体**：`GHSA-mcmc-2m55-j8jj` / `fixed_by` / `vllm@0.13.0`
- **候选值**：`{"package": "vllm", "fixed_version": "0.13.0"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-FV-PARSE: 0.13.0 可解析为版本；R-FV-CONSISTENCY: fixed=0.13.0 不落在受影响区间 >= 0.10.2, < 0.13.0；R-FV-SNAPSHOT: 原始快照 包含 '0.13.0' 的版本号；R-FV-STRUCTURED: OSV 结构化事件 fixed=['0.13.0']，候选='0.13.0'
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/05825c4e086d5563d928d48dfc7ed4ddfe492567ca5a781d878e4ccc8817371c.json → affected[].ranges[].events[].fixed`

**证据片段（原文）**：

```
{"package": "vllm", "ranges": {"type": "ECOSYSTEM", "events": [{"introduced": "0.10.2"}, {"fixed": "0.13.0"}]}}
```

**自动规则明细**：
- `R-FV-PARSE=pass: 0.13.0 可解析为版本`
- `R-FV-CONSISTENCY=pass: fixed=0.13.0 不落在受影响区间 >= 0.10.2, < 0.13.0`
- `R-FV-SNAPSHOT=pass: 原始快照 包含 '0.13.0' 的版本号`
- `R-FV-STRUCTURED=pass: OSV 结构化事件 fixed=['0.13.0']，候选='0.13.0'`

**需要人工确认的问题**：
1. OSV 声明的 fixed 是否为 0.13.0？
1. 受影响区间的下界是否为 0（即所有早期版本都受影响）？
1. 该修复版本与候选的 package/ecosystem 是否对应同一产品？

**判定规则**：对照来源公告原文，确认修复版本号与受影响区间不矛盾。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

## 二、CVSS（22 条）

### BREL-CV-0001 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-41106` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:N/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 9.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:N/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=9.3 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-41106].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：Microsoft 365 Copilot Elevation of Privilege Vulnerability｜CVSSScoreSets=[{"BaseScore": 9.3, "TemporalScore": 8.1, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:N/E:U/RL:O/RC:C", "ProductID": ["16765"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=9.3 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=8.1；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=9.3 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0002 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-41109` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 8.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=8.8 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-41109].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：GitHub Copilot and Visual Studio Code Security Feature Bypass Vulnerability｜CVSSScoreSets=[{"BaseScore": 8.8, "TemporalScore": 7.7, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H/E:U/RL:O/RC:C", "ProductID": ["11622"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=8.8 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=7.7；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=8.8 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0003 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-45499` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 9.9, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=9.9 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-45499].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：Azure OpenAI Elevation of Privilege Vulnerability｜CVSSScoreSets=[{"BaseScore": 9.9, "TemporalScore": 8.6, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H/E:U/RL:O/RC:C", "ProductID": ["12286"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=9.9 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=8.6；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=9.9 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0004 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-47282` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:N/A:N/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 6.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:N/A:N/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=6.5 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-47282].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：GitHub Copilot and Visual Studio Code Information Disclosure Vulnerability｜CVSSScoreSets=[{"BaseScore": 6.5, "TemporalScore": 5.7, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:N/A:N/E:U/RL:O/RC:C", "ProductID": ["11622"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=6.5 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=5.7；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=6.5 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0005 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-50510` / `has_cvss` / `CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 7.8, "vector": "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=7.8 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-50510].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：GitHub Copilot Remote Code Execution Vulnerability｜CVSSScoreSets=[{"BaseScore": 7.8, "TemporalScore": 6.8, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H/E:U/RL:O/RC:C", "ProductID": ["20677"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=7.8 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=6.8；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=7.8 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0006 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-50517` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 9.9, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=9.9 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-50517].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：Microsoft M365 Copilot Remote Code Execution Vulnerability｜CVSSScoreSets=[{"BaseScore": 9.9, "TemporalScore": 8.6, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H/E:U/RL:O/RC:C", "ProductID": ["16765"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=9.9 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=8.6；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=9.9 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0007 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-55145` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:U/C:H/I:L/A:N/E:P/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 6.3, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:U/C:H/I:L/A:N/E:P/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=6.3 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-55145].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：Outlook Copilot Tampering Vulnerability｜CVSSScoreSets=[{"BaseScore": 6.3, "TemporalScore": 5.7, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:U/C:H/I:L/A:N/E:P/RL:O/RC:C", "ProductID": ["21063"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=6.3 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=5.7；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=6.3 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0008 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-56167` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 8.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=8.5 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-56167].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：Azure AI Search Elevation of Privilege Vulnerability｜CVSSScoreSets=[{"BaseScore": 8.5, "TemporalScore": 7.4, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N/E:U/RL:O/RC:C", "ProductID": ["12318"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=8.5 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=7.4；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=8.5 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0009 · cvss

- **主体 / 关系 / 客体**：`CVE-2026-58617` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:N/E:U/RL:O/RC:C`
- **候选值**：`{"version": "3.1", "score": 8.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:N/E:U/RL:O/RC:C"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=8.1 在 0–10；R-CV-VECTOR: vector 含 11 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-58617].CVSSScoreSets`

**证据片段（原文）**：

```
文档：July 2026 Security Updates｜标题：M365 Copilot for iOS Elevation of Privilege Vulnerability｜CVSSScoreSets=[{"BaseScore": 8.1, "TemporalScore": 7.1, "EnvironmentalScore": 0, "Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:N/E:U/RL:O/RC:C", "ProductID": ["21043"], "IsTemporalScoreFieldSpecified": false}]
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=8.1 在 0–10`
- `R-CV-VECTOR=pass: vector 含 11 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- 该记录带 TemporalScore=7.1；候选只保存 BaseScore，需确认口径是基础分还是时序分。

**需要人工确认的问题**：
1. 候选 score=8.1 是否等于 MSRC 的 BaseScore？
1. 候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？
1. 候选 version 与向量前缀（如 CVSS:3.1）是否一致？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0010 · cvss

- **主体 / 关系 / 客体**：`PYSEC-2026-4000` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/08e1baad2cecde5d9a5c797c318722171dc9832e7329304d9d746947f074b934.json → severity[].score`

**证据片段（原文）**：

```
OSV id=PYSEC-2026-4000｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N"}]｜summary/details=vLLM through 0.29.0 fails to properly validate bad_words token indices against the model's generation output width in SamplingParams.update_from_tokenizer(). Attackers can supply out-of-bounds token indices that corrupt logits memory of concurrent requests, causing different in-flight HTTP requests to return incorrect  …（已截断）
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0011 · cvss

- **主体 / 关系 / 客体**：`PYSEC-2026-3998` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/b9440e819799ff3b43e23a164d61ffdf6be3e85ba4a69cc1799236d645645462.json → severity[].score`

**证据片段（原文）**：

```
OSV id=PYSEC-2026-3998｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N"}]｜summary/details=vLLM before 0.29.0 validates allowed_token_ids against tokenizer length instead of model output logits width in SamplingParams._validate_allowed_token_ids(). Attackers can supply token IDs above the output vocabulary that pass validation, causing LogitBiasState to corrupt GPU logits state and allow concurrent requests  …（已截断）
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0012 · cvss

- **主体 / 关系 / 客体**：`PYSEC-2026-3999` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/c30815fb9f87727ed13e2729ac5f69bdc2bf2e4333466f7c08d79f123407d524.json → severity[].score`

**证据片段（原文）**：

```
OSV id=PYSEC-2026-3999｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N"}]｜summary/details=vLLM through 0.29.0 contains a memory corruption vulnerability in the Triton _bincount_kernel where prompt token IDs index the penalty prompt-presence bitset without bounds checking against vocabulary size. Attackers can submit multimodal audio requests with tokens equal to vocabulary size, causing out-of-bounds writes …（已截断）
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0013 · cvss

- **主体 / 关系 / 客体**：`PYSEC-2026-3997` / `has_cvss` / `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X`
- **候选值**：`{"version": "4.0", "score": null, "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 32 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/5f29c77279f71baaaa32e4a071dc6a660e7b7af485d346508b4418c3b8806550.json → severity[].score`

**证据片段（原文）**：

```
OSV id=PYSEC-2026-3997｜severity=[{"type": "CVSS_V4", "score": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X"}]｜summary/details=vLLM versions before 0.28.0 fail to validate the lower bound of token IDs in the /v1/embeddings and /pooling endpoints, allowing unauthenticated attackers to crash the engine by submitting negative token IDs. A single reque …（已截断）
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 32 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0014 · cvss

- **主体 / 关系 / 客体**：`PYSEC-2026-3996` / `has_cvss` / `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X`
- **候选值**：`{"version": "4.0", "score": null, "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 32 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/b478fb82de5d93e18084254420bbfc703a0b6e84ba2c20bab6907f5cbd8cdebb.json → severity[].score`

**证据片段（原文）**：

```
OSV id=PYSEC-2026-3996｜severity=[{"type": "CVSS_V4", "score": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X"}]｜summary/details=vLLM through 0.29.0 fails to properly clean up decode-side metadata for rejected inference requests in prefill/decode disaggregated deployments. Remote attackers can submit requests with max_tokens=0 to exhaust decode-worke …（已截断）
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 32 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0015 · cvss

- **主体 / 关系 / 客体**：`GHSA-8pw2-6jv3-mj5j` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/5ec93b0e68589ed193d2c5bbeb1f7edc0bf869edce96a714ec8c500d02fc1cb3.json → severity[].score`

**证据片段（原文）**：

```
OSV id=GHSA-8pw2-6jv3-mj5j｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H"}]｜summary/details=vLLM: Request-selected PyNvVideoCodec GPU decode bypasses static VRAM reservation
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0016 · cvss

- **主体 / 关系 / 客体**：`GHSA-hcwq-8wjf-3gcr` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/1f26b5e5797b4057a910378c02a1139671eae131bf4560cf65b9328528ab9646.json → severity[].score`

**证据片段（原文）**：

```
OSV id=GHSA-hcwq-8wjf-3gcr｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H"}]｜summary/details=vLLM: Unauthenticated audio decompression-bomb DoS in /v1/chat/completions
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0017 · cvss

- **主体 / 关系 / 客体**：`PYSEC-2026-3985` / `has_cvss` / `CVSS:4.0/AV:L/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X`
- **候选值**：`{"version": "4.0", "score": null, "vector": "CVSS:4.0/AV:L/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 32 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/a2f3f13da0780b28558d193546127b1ecda72a69c89a1cec62a970930b66d5b7.json → severity[].score`

**证据片段（原文）**：

```
OSV id=PYSEC-2026-3985｜severity=[{"type": "CVSS_V4", "score": "CVSS:4.0/AV:L/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X"}]｜summary/details=vLLM before 0.28.0 contains a remote code execution vulnerability in the LlavaOnevision2 processor loader that ignores the trust_remote_code parameter when loading remote processor classes. Attackers can craft a malicious m …（已截断）
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 32 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:4.0/AV:L/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:H…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0018 · cvss

- **主体 / 关系 / 客体**：`GHSA-wvm9-9g5j-623f` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/579265ef2af27fecd42dde2e00017f2b6aa834e84348ec5d19f2eb2be471355b.json → severity[].score`

**证据片段（原文）**：

```
OSV id=GHSA-wvm9-9g5j-623f｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"}]｜summary/details=Open WebUI: Users denied by the OAuth role policy can still sign in via token exchange
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0019 · cvss

- **主体 / 关系 / 客体**：`GHSA-3g9q-v48f-hh9w` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/943ad60707eae33503855dc72e69353747fb3ebfa105a9579e2bae6f9ae5dac1.json → severity[].score`

**证据片段（原文）**：

```
OSV id=GHSA-3g9q-v48f-hh9w｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"}]｜summary/details=Open WebUI: Unauthenticated requests can stall the server via uncached OIDC fetches in back-channel logout
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0020 · cvss

- **主体 / 关系 / 客体**：`GHSA-v39v-59xw-j98g` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:L`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:L"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/7f6b0730c264a3430be3c50a000a1e6ccf8a04e69fba1d3f48c8b01eb616aedf.json → severity[].score`

**证据片段（原文）**：

```
OSV id=GHSA-v39v-59xw-j98g｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:L"}]｜summary/details=Open WebUI: Any authenticated user can suppress calendar alerts instance-wide via a non-numeric alert value
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:L…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0021 · cvss

- **主体 / 关系 / 客体**：`GHSA-mcmc-2m55-j8jj` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H`
- **候选值**：`{"version": "3.1", "score": null, "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H"}`
- **自动核验**：`supported`（medium）
- **自动理由**：R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=未命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/osv/05825c4e086d5563d928d48dfc7ed4ddfe492567ca5a781d878e4ccc8817371c.json → severity[].score`

**证据片段（原文）**：

```
OSV id=GHSA-mcmc-2m55-j8jj｜severity=[{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H"}]｜summary/details=vLLM introduced enhanced protection for CVE-2025-62164
```

**自动规则明细**：
- `R-CV-RANGE=unavailable: 来源未给出数值分数（不得当作 0）`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=未命中`

**⚠️ 冲突提示**：
- 候选只保存了向量、未保存基础分（score=null），无法核对分数。

**需要人工确认的问题**：
1. OSV severity 中的向量是否为 CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H…？
1. 候选 score=null 是「上游未提供基础分」还是「采集遗漏」？
1. 候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-CV-0022 · cvss

- **主体 / 关系 / 客体**：`CVE-2025-9959` / `has_cvss` / `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:H/A:L`
- **候选值**：`{"version": "3.1", "score": 7.6, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:H/A:L"}`
- **自动核验**：`supported`（high）
- **自动理由**：R-CV-RANGE: score=7.6 在 0–10；R-CV-VECTOR: vector 含 8 个度量项，前缀正确；R-CV-SNAPSHOT: 原始快照 vector=命中 score=命中
- **证据状态**：**direct**
- **证据定位**：`snapshots/nvd/6b69782b9647694c021150ed8f3f1d9821217e1a81613367437425954b7884b9.json → cve[CVE-2025-9959].metrics.*[].cvssData`

**证据片段（原文）**：

```
NVD cve=CVE-2025-9959｜描述：Incomplete validation of dunder attributes allows an attacker to escape from the Local Python execution environment sandbox, enforced by smolagents. The attack requires a Prompt Injection in order to trick the agent to create malicious code.｜metrics=[{"metric": "cvssMetricV31", "source": "reefs@jfrog.com", "type": "Secondary", "cvssData": {"version": "3.1", "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:H/A:L", "baseScore": 7.6, "baseSeverity …（已截断）
```

**自动规则明细**：
- `R-CV-RANGE=pass: score=7.6 在 0–10`
- `R-CV-VECTOR=pass: vector 含 8 个度量项，前缀正确`
- `R-CV-SNAPSHOT=pass: 原始快照 vector=命中 score=命中`

**⚠️ 冲突提示**：
- NVD 该条仅由 Secondary 来源（非 NVD 自评）提供 CVSS。

**需要人工确认的问题**：
1. 候选 score=7.6 是否等于 NVD 的 baseScore？
1. 候选 vector 与 NVD vectorString 是否逐字一致？
1. 该 CVSS 记录来自 Primary 还是 Secondary 来源，是否可接受？

**判定规则**：对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---
