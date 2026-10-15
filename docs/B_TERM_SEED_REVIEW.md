# B 项术语种子表领域复核（2026-10-14）

**结论**：对照赛题四类风险复核了原有 14 个种子，**补入 12 条**（种子总数 14 → 26）。
只加种子条目，匹配机制（`_alias_pattern` / `entries()` / `coverage()` / `term_edges()`）
一个字符都没改。每条新增都实测过"语料里是否真的出现"，命中为 0 的一律没有加。

## 1. 复核前的问题：四类风险的覆盖失衡

| 赛题风险类别 | 原种子数 | 原有条目 | 复核后 |
| --- | --- | --- | --- |
| AI 基础设施 | 1 | `mcp` | **4** |
| 模型与数据层风险 | 4 | `prompt_injection` / `jailbreak` / `data_poisoning` / `prompt_leakage` | **8** |
| AI 应用与智能体风险 | 2 | `multi_agent` / `tool_calling` | **5** |
| 供应链风险 | 1 | `supply_chain` | **3** |

（另有 `rag` / `graphrag`（技术方案）、`auroc` / `false_positive`（评测方法）、
`cvss` / `poc`（情报标准）6 条不属于四类风险，未动。）

最薄的两类是**基础设施**与**供应链**，各只有 1 条；而语料里这两类恰恰是命中较多的
（推理框架、模型分发节点）。模型与数据层则缺了**隐私攻击**这一整类。

## 2. 新增的 12 条（均含语料实测命中）

命中数在 **B 评测语料** `D:\ICT\intel-data-b`（3,639 个分块 + 93 个事件 = 3,732 条记录）
上用字典自身的匹配规则量得，格式为"命中文档数 / 命中记录数"。

| key | 术语 | 类别 | 命中文档 / 记录 | 加入理由 |
| --- | --- | --- | --- | --- |
| `indirect_prompt_injection` | indirect prompt injection | 模型与数据层风险 | 3 / 5 | 注入指令来自被检索或被访问的外部内容，与现有的直接注入是两个攻击面 |
| `data_leakage` | data leakage / data exfiltration | 模型与数据层风险 | 6 / 8 | 训练与推理数据被带出模型边界，与"只泄漏系统提示"的提示词泄漏不同 |
| `membership_inference` | membership inference | 模型与数据层风险 | 1 / 1 | 判断样本是否在训练集内的经典模型隐私攻击，此前整类缺失 |
| `model_inversion` | model inversion | 模型与数据层风险 | 1 / 2 | 通过查询重建训练样本特征；与成员推断同族但机制不同（重建 vs 判定） |
| `multi_agent_collusion` | multi-agent collusion | AI 应用与智能体风险 | 2 / 18 | 多智能体互相配合绕过各自约束；语料里有专门讨论该问题的论文 |
| `tool_poisoning` | tool poisoning | AI 应用与智能体风险 | 1 / 4 | 被污染的工具描述或返回值操纵智能体，与提示词注入同源但发生在工具层 |
| `excessive_agency` | excessive agency | AI 应用与智能体风险 | 2 / 3 | 智能体被授予超出任务所需的权限与动作空间 |
| `sandbox_escape` | sandbox escape | AI 基础设施 | 5 / 5 | 执行智能体代码或工具的环境被突破；基础设施类此前只有 MCP 一条 |
| `vllm` | vLLM | AI 基础设施 | 11 / 18 | 语料里命中文档数最多的推理框架；关系评测的多数生态事件也落在它的版本区间上 |
| `ollama` | Ollama | AI 基础设施 | 3 / 24 | 语料覆盖面很广的本地模型运行时，也是模型链"没有本地模型层"这条说明的对照面 |
| `hugging_face` | Hugging Face | 供应链风险 | 10 / 39 | 模型与数据集的集中分发节点，供应链类里命中最多 |
| `malicious_package` | malicious package | 供应链风险 | 1 / 4 | 供应链攻击最常见的落地形态；发生在分发环节而不是训练数据 |

复核后的整体覆盖（同一份语料）：

```
terms: 26   covered_terms: 25   uncovered_terms: [graphrag]   documents_referenced: 37
```

## 3. 评估过但不加的（附实测依据）

任务书点名的候选里，有几条在这份语料里**确实不出现**，按"出现不了的不要加"处理：

| 候选术语 | 命中 | 不加的理由 |
| --- | --- | --- |
| model extraction / model stealing | 0 / 0 | 语料里没有任何写法命中；模型窃取这一面语料没覆盖 |
| RAG poisoning / knowledge-base poisoning | 0 / 0 | 同上；检索库投毒在语料中未出现 |
| agent hijacking | 0 / 0 | 同上 |
| prompt leaking | **0 / 0** | 语料里只有 `prompt leakage`，没有 `prompt leaking` 这种写法 |
| 提示词泄漏 / 提示词泄露（中文） | 0 / 0 | 中文写法一次都没出现 |
| container escape | 0 / 0 | 只有 `sandbox escape`，容器逃逸这种写法没有 |
| dependency confusion | 0 / 0 | 未出现 |
| SBOM / 软件物料清单 | 0 / 0 | 未出现（资产侧用 CycloneDX 导入，但语料文本里没有该词） |
| pickle / 序列化攻击 | 0 / 0 | 未出现 |
| adversarial example / perturbation | 0 / 0 | 未出现 |
| goal hijacking / goal misalignment | 0 / 0 | 未出现 |
| typosquatting | 1 / 1 | 与 `malicious_package` 同属分发环节，仅 1 条记录，先不单独成条 |
| model card | 2 / 3 | 是治理文档而不是风险面，四类风险里没有它的位置 |
| guardrail | 5 / 33 | 属防护机制（防御项），不是风险面；若将来单列"防护"维度再加 |

### 3.1 关于 prompt leaking 与 system prompt leakage 的区别

这是任务书点名要判清的一处。逐别名实测（同一份语料）：

| 写法 | 命中记录 / 文档 | 说明 |
| --- | --- | --- |
| `prompt leakage` | 2 / 2 | 出现，是现有种子 `prompt_leakage` 的主别名 |
| `prompt leaking` | **0 / 0** | 不出现 |
| `system prompt leakage` | 2 / 2 | 出现 |
| `system prompt` | 18 / 6 | 出现，是命中数的主要来源 |
| `提示词泄漏` / `提示词泄露` | 0 / 0 | 中文写法都不出现 |

结论：语料里能站住的说法是 `prompt leakage` 与 `system prompt leakage`，
**"prompt leaking" 与中文写法都没有命中**。因此现有种子的别名表已经足够表达这一面，
**不需要为这两种写法新增别名或条目**；中文别名保留不动（它对当前语料命中为 0，
但不会造成误命中，语料扩充后可直接生效），也符合"只加种子、不改机制"的边界。

## 4. 复核怎么做的

* 用字典**自身的**匹配规则（`_alias_pattern`：ASCII 走词边界、CJK 走子串）在
  B 评测语料的**分块 + 事件**两类记录上逐条搜索，因此这里报的命中数与字典页面
  `GET /api/knowledge/terms` 是同一套算法。
* 每条候选都先量命中，再决定加不加；命中为 0 的一律不加。
* 没有改匹配机制，也没有为了让某个术语"看起来被覆盖"而放宽别名。

## 5. 两套覆盖数：各自对应哪份语料

同一个种子表在两份不同语料上会得到不同的覆盖数，**两套都成立，不是矛盾**：

| 口径 | 语料 | 种子 | 覆盖 | 关联文档 | 未覆盖 | 用途 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 本复核（B 评测语料） | `D:\ICT\intel-data-b`：22 文档 / 3,639 分块 + 93 事件 | 26 | **25** | **37** | 仅 `graphrag` | 核对**种子表内容**：这个词在语料里到底有没有出现 |
| 演示机（页面与报告口径） | 演示机 `data/intel.sqlite`：638 事件 / 1 文档 / 849 分块 | 26 | **18** | **82** | auroc、cvss、excessive_agency、graphrag、malicious_package、model_inversion、tool_calling、tool_poisoning | 页面 `GET /api/knowledge/terms` 与报告附录 A 的实际展示值 |

**为什么差这么多**：两份语料的内容构成不同。评测语料以 22 篇论文 + 93 个事件为主，
`auroc` / `cvss` / `tool_calling` / `excessive_agency` 这类出现在论文正文里的术语容易被命中；
演示机库以 638 个事件为主、只有 1 个全文文档，逐条命中面更宽但结构不同，
所以"关联文档"从 37 变成 82、覆盖数从 25 变成 18。

**引用规则**：报告与 PPT 引用"术语字典覆盖数"时一律用**演示机口径**（覆盖 18 / 种子 26 / 关联 82），
因为它与页面同源；本复核的 25 / 26 / 37 只在讨论"种子表内容是否合理"时引用，并须注明语料。

**其余局限**

* 覆盖数随语料增长而变。任务书第一次记的 14 / 10 / 44 是 2026-10-14 的演示机读数，
  现在同一口径是 26 / 18 / 82——**变的是语料与种子表，算法没有变**；刷新方式是重取 `GET /api/knowledge/terms`。
* `graphrag` 在两份语料里都未覆盖，保持未覆盖、不补写释义——这是字典本来的设计。
