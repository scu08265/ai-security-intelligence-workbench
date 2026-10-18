# B5 逐题初判（2026-10-18 模型批次）

**性质**：队长按 B 的同一份 rubric 逐题初判，AI 辅助整理；`人工签字` 列保持空白。
签字确认前不进入页面，也不替代 20261012 活动批次。

## 结果

| 指标 | 10-12 旧批次 | 10-18 模型批次（建议） |
| --- | --- | --- |
| 答案正确率 | 6/38 = 15.79% | **24/38 = 63.16%** |
| 已判定内正确率 | 6/9 = 66.67% | **24/28 = 85.71%** |
| 部分正确（partial） | 29 | 10 |
| 引用支持率 | 4/36 = 11.11% | **24/38 = 63.16%** |
| 拒答召回 | 4/12 = 33.33% | **8/12 = 66.67%** |

## 本轮修掉的三类问题

1. **列举题**：问“哪些文档/论文”时改为列出实际命中的文档标题与 chunk，不再答成一篇综述。
2. **定义/方法题**：事件摘要会让位给文档证据；网页导航块（Skip to content 等）不再当证据。
3. **点名对象不在事件里**：改用文档证据作答，不再拿无关论文凑数。

## 仍然失败（4 道 incorrect + 10 道 partial）

- `BQA-013` kernel-level evidence：命中的是背景段，未给定义。
- `BQA-015` AUROC 定义：语料里只有结果表片段，系统拒答。
- `BQA-017` 蜜罐部署位置：语料未给出部署位置，系统拒答。
- `BQA-039` 多跳交集：应拒答却给出无关 CVE。
- 10 道 partial 主要是列举不完整（只列 1–2 份）或只回标题未展开。

## 文件与启用

- 逐题判定：`artifacts/b_eval/B5_ADJUDICATION_PROPOSAL_20261018.csv`
- 建议分数：`artifacts/b_eval/qa_human_score_20261018_proposed.json`
- 复跑结果：`artifacts/b_eval/formal_qa_results_20261018_model.json`

签字后把 `_proposed` 去掉即切换批次：

```powershell
Copy-Item artifacts\b_eval\qa_human_score_20261018_proposed.json artifacts\b_eval\qa_human_score_20261018.json
```