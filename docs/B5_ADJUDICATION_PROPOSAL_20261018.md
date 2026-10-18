# B5 逐题初判（2026-10-18 模型批次）

**性质**：队长按 B 的同一份 rubric 逐题初判，AI 辅助整理；`人工签字` 列保持空白。
签字确认前不进入页面，也不替代 20261012 活动批次。

## 结果

| 指标 | 10-12 旧批次 | 10-18 模型批次（建议） |
| --- | --- | --- |
| 答案正确率 | 6/38 = 15.79% | **25/38 = 65.79%** |
| 已判定内正确率 | 6/9 = 66.67% | **25/28 = 89.29%** |
| 部分正确（partial） | 29 | 10 |
| 引用支持率 | 4/36 = 11.11% | **25/38 = 65.79%** |
| 拒答召回 | 4/12 = 33.33% | **12/12 = 100.00%** |

## 本轮修掉的四类问题

1. **列举题**：问“哪些文档/论文”时列出实际命中的文档标题与 chunk，不再答成一篇综述。
2. **定义与方法题**：事件摘要让位给文档证据；网页导航块（Skip to content 等）不再当证据。
3. **位置题**：问“部署在哪里”时给查询补 located / deployed / location，
   于是能命中原文的 “DigitalOcean honeypots are located in Frankfurt”。
4. **跨清单交集题**：在检索前短路成拒答，不再用一条无关 CVE 冒充交集结果。
5. **对应关系与宽泛查询**：“与…对应/匹配”按交集处理；单个通用词（vulnerability / security）
   先要求补充具体对象，不再随手抓一条记录作答。

## 仍然失败的 6 道

答案错误 3 道（语料本身缺内容）：

- `BQA-005` EAGER 的奖励机制：语料只有结果数字，没有机制描述。
- `BQA-013` kernel-level evidence：论文未给出成句定义，命中段落都是背景。
- `BQA-015` AUROC 定义：语料只有实验表格里的用法，没有指标定义。

拒答判定：12 道全部正确。

这 3 道需要补语料才能答对，不属于答案组织的修复范围。

## 文件与启用

- 逐题判定：`artifacts/b_eval/B5_ADJUDICATION_PROPOSAL_20261018.csv`
- 建议分数：`artifacts/b_eval/qa_human_score_20261018_proposed.json`
- 复跑结果：`artifacts/b_eval/formal_qa_results_20261018_model.json`

签字后把 `_proposed` 去掉即切换批次：

```powershell
Copy-Item artifacts\b_eval\qa_human_score_20261018_proposed.json artifacts\b_eval\qa_human_score_20261018.json
```
