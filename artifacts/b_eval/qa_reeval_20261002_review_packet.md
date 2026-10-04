<!-- 由 tools/build_b_qa_reeval_review_packet.py 生成；机器建议为 B 类，人工标签需人工填写 -->

# B 任务问答重评测 · 人工确认清单（2026-10-02 批次）

本清单覆盖**全部 50 题**，用于一次性人工裁定。所有“机器建议”均为 B 类（机器辅助建议），**不是**人工金标准；人工列请填 `artifacts/b_eval/qa_final_confirmation_worksheet_20261002.csv` 的三个`人工判定_*` 列。

- 答案与引用与改造前逐字一致：**16 题**（可批量确认是否沿用旧标签）
- 有变化且非争议：**30 题**
- 争议口径或拒答行为翻转：**11 题**

标签口径：答案正确性 `correct / partial / incorrect / unknown / not_applicable`；引用支持性 `supported / partially_supported / unsupported / not_applicable / unknown`；拒答正确性 `correct / incorrect / not_applicable / unknown`。`partial`、`unknown` 不计为正确；空值不计入分母。

## 一、与改造前逐字一致的题（批量确认）

| 题号 | 题型 | 改造前人工标签（答/引/拒） | 机器建议（答/引/拒） |
| --- | --- | --- | --- |
| BQA-008 | 基础事实问答 | correct / not_applicable / not_applicable | partial / not_applicable / correct |
| BQA-013 | 术语及语义查询 | partial / partially_supported / not_applicable | partial / unknown / correct |
| BQA-018 | 术语及语义查询 | partial / partially_supported / not_applicable | correct / unknown / correct |
| BQA-022 | 中英文混合查询 | partial / partially_supported / not_applicable | partial / unknown / correct |
| BQA-024 | 中英文混合查询 | partial / partially_supported / not_applicable | partial / unknown / correct |
| BQA-027 | 多轮追问 | incorrect / not_applicable / not_applicable | partial / not_applicable / correct |
| BQA-033 | 跨文档问答 | partial / partially_supported / not_applicable | partial / unknown / correct |
| BQA-035 | 跨文档问答 | partial / partially_supported / not_applicable | partial / unknown / correct |
| BQA-036 | 跨文档问答 | correct / partially_supported / not_applicable | partial / unknown / correct |
| BQA-037 | 跨文档问答 | incorrect / unsupported / not_applicable | partial / unknown / correct |
| BQA-041 | 无证据问题与范围外问题 | （空） / not_applicable / correct | not_applicable / not_applicable / correct |
| BQA-042 | 无证据问题与范围外问题 | （空） / not_applicable / correct | not_applicable / not_applicable / correct |
| BQA-043 | 无证据问题与范围外问题 | （空） / not_applicable / correct | not_applicable / not_applicable / correct |
| BQA-045 | 无证据问题与范围外问题 | （空） / not_applicable / correct | not_applicable / not_applicable / correct |
| BQA-046 | 拒答及证据不足 | （空） / not_applicable / incorrect | not_applicable / not_applicable / incorrect |
| BQA-050 | 拒答及证据不足 | （空） / not_applicable / incorrect | not_applicable / not_applicable / incorrect |

## 二、有变化、无口径争议的题

### BQA-001｜基础事实问答｜应作答｜变化：答案文本有变；引用有变

- 问题：DistillGuard 这篇论文的标题是什么？
- 预期：文档 ['paper:2609.28996']；要点 ['DistillGuard', 'NPM']
- 系统实际：作答（耗时 523.3 ms）
- 系统回答：检索到的原文直接证据： - “the Node.js ecosystem; however, its open-source supply chain this paper presents a research study on the detection of ma” [DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis via Static Graph and LLM Distillation · chunk-1d587a2277136ea8af37acfc] - “Question: Does the paper descri …
- 引用（4 条）：
    - `chunk-1d587a2277136ea8af37acfc` @ doc-6848cfa4c508d3d98cbcc747：valu- crafted rules; consequently, they suffer from limited gener- able insights for NPM supply chain security …
    - `chunk-4607af632c4a1e1728692fa0` @ doc-6848cfa4c508d3d98cbcc747：structure into structured regulatory labels. Finally, we employ an efficient LoRA parameter fine-tuning strate …
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（4 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-002｜基础事实问答｜应作答｜变化：答案文本有变；引用有变

- 问题：OllamaDrama 论文研究的是什么对象？
- 预期：文档 ['paper:2609.29757']；要点 ['OllamaDrama', 'honeypot']
- 系统实际：作答（耗时 482.2 ms）
- 系统回答：检索到的原文直接证据： - “Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.05530, 2024.” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-a785e777ad83e7d8cb364c69] - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-H …
- 引用（5 条）：
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
    - `chunk-e7c4f5f3c7751a3ffa30b7ce` @ doc-e16f7d33561d58da8e56e445：full range of specialized LLM API endpoints. Our work aims to address this gap by introducing a dedicated hone …
- 机器建议（B 类）·答案正确性：**partial**（suggested，low）—— 预期文档或预期要点只有一项命中，可能遗漏关键条件
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-003｜基础事实问答｜应作答｜变化：答案文本有变；引用有变

- 问题：Codetta 论文研究的是什么问题？
- 预期：文档 ['paper:2609.28900']；要点 ['Codetta', 'collusion']
- 系统实际：作答（耗时 501.1 ms）
- 系统回答：检索到的原文直接证据： - “Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.05530, 2024.” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-a785e777ad83e7d8cb364c69] - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-H …
- 引用（4 条）：
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
- 机器建议（B 类）·答案正确性：**unknown**（pending_human_review，low）—— 有引用但未命中预期文档/要点；引用内容是否等价于题目要求需人工判断
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-004｜基础事实问答｜应作答｜变化：答案文本有变；引用有变

- 问题：SAGE 这篇论文的方法名称是什么？
- 预期：文档 ['paper:2609.30192']；要点 ['SAGE', 'Topological']
- 系统实际：作答（耗时 496.4 ms）
- 系统回答：检索到的原文直接证据： - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance · chunk-5c35e2d194d9c97348a5e958] - “Under review as a conference paper at ICLR 2027” [Just Ask Jev: Reinforcement Learning for Calibrated De …
- 引用（5 条）：
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
    - `chunk-03317ba315f16be669e3c769` @ doc-52378c1633f50c6eb3b600e4：soning as a stress test for exploration and compounding biases. Section 5.4 is the ablation study of the two c …
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=correct；引用=partially_supported；拒答=not_applicable

### BQA-005｜基础事实问答｜应作答｜变化：答案文本有变；引用有变

- 问题：EAGER 论文使用了什么奖励机制？
- 预期：文档 ['paper:2609.29230']；要点 ['EAGER', 'Verifiable Rewards']
- 系统实际：作答（耗时 509.8 ms）
- 系统回答：根据检索到的原文证据： - “Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.05530, 2024.” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-a785e777ad83e7d8cb364c69] - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-H …
- 引用（4 条）：
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
- 机器建议（B 类）·答案正确性：**unknown**（pending_human_review，low）—— 有引用但未命中预期文档/要点；引用内容是否等价于题目要求需人工判断
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-006｜基础事实问答｜应作答｜变化：答案文本有变；引用有变

- 问题：NeRD 论文的应用领域是什么？
- 预期：文档 ['paper:2606.15617']；要点 ['NeRD', 'Medical']
- 系统实际：作答（耗时 470.8 ms）
- 系统回答：检索到的原文直接证据： - “expert study to assess the clinical plausibility, showing that NeRD rationales” [NeRD: Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded Chain-of-Thought in Medical Image Diagnosis · chunk-5c71aaa24bd8d7056ac0313a] - “Under review as a conference paper at ICLR” [Just Ask Jev: Reinforcement …
- 引用（5 条）：
    - `chunk-5c71aaa24bd8d7056ac0313a` @ doc-70c35c725fef8799991500f8：NeRD 3 Fig.2: Framework of our method. Step 1: Induce a diagnostic rule set from concepts. Step 2: Execute Neu …
    - `chunk-6ece9563486747c798438a8e` @ doc-70c35c725fef8799991500f8：r all items to obtain a mean score per method. Main Results.Fig. 3(b) summarizes the results of the human expe …
    - `chunk-7b3ba17746f32905b1b37285` @ doc-70c35c725fef8799991500f8：xisting concept-driven interpretable methods have key limitations: Concept Bottleneck Models (CBMs) require sc …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=correct；引用=partially_supported；拒答=not_applicable

### BQA-007｜基础事实问答｜应作答｜变化：答案文本有变

- 问题：Hard Stop 论文关注什么样的执行被抢先终止？
- 预期：文档 ['paper:2609.29808']；要点 ['Hard Stop', 'Preemption']
- 系统实际：作答（耗时 573.4 ms）
- 系统回答：根据检索到的原文证据： - “Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint” [Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution · chunk-9aa9b7f0bfc461185e805840]
- 引用（5 条）：
    - `chunk-9aa9b7f0bfc461185e805840` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint # 2. Template Injection & Traversal  …
    - `chunk-40e6485386bfdf62a9f37df0` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint } exceptException: pass returnNone d …
    - `chunk-dd6697dfa7ef5bd2eb0080ec` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint defterminate_process_group(self)->bo …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-009｜基础事实问答｜应作答｜变化：引用有变

- 问题：Parameter-Efficient Fine-Tuning 这篇论文的主题是什么？
- 预期：文档 ['paper:2501.13787']；要点 ['Parameter-Efficient', 'Fine-Tuning']
- 系统实际：作答（耗时 510.6 ms）
- 系统回答：OPENALEX-W4406794439：Parameter-Efficient Fine-Tuning for Foundation Models
- 引用（5 条）：
    - `chunk-1c81026ab5a957ec178913c4` @ doc-086c0557444be72ddfb3c0fd：[32]Y. Xin, S. Luo, H. Zhou, J. Du, X. Liu, Y. Fan, B. Ommer, “High-resolution image synthesis with latent Q.  …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
    - `chunk-cd88706791b637f4ceb17531` @ doc-086c0557444be72ddfb3c0fd：icates that the structure of FMS has changed, Position denotes the fine-tuned parameter position,arXiv, 2019LL …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=unknown；拒答=not_applicable

### BQA-010｜基础事实问答｜应作答｜变化：答案文本有变；引用有变

- 问题：JevOut 论文的主题是什么？
- 预期：文档 ['paper:2609.30243']；要点 ['JevOut']
- 系统实际：作答（耗时 461.2 ms）
- 系统回答：检索到的原文直接证据： - “Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.05530, 2024.” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-a785e777ad83e7d8cb364c69] - “study of position bias in LLM-as-a-judge.” [JevOut: Natural Context Can Flip Decision Models · chunk-c75e38333dc6f5 …
- 引用（4 条）：
    - `chunk-c75e38333dc6f5f433422c0f` @ doc-f284aa21daa99b65a0902fd1：study of position bias in LLM-as-a-judge. In Proceedings of the 14th International Joint Conference on Natural …
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（4 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=correct；引用=partially_supported；拒答=not_applicable

### BQA-011｜术语及语义查询｜应作答｜变化：答案文本有变

- 问题：什么是提示词注入？
- 预期：文档 ['source:owasp_genai']；要点 ['Prompt Injection']
- 系统实际：作答（耗时 432.0 ms）
- 系统回答：检索到的原文直接证据： - “While prompt injection and jailbreaking are related concepts in LLM security, they are often used interchangeably.” [owasp_genai · chunk-90c768cd5de7c577f26397d2]
- 引用（6 条）：
    - `chunk-90c768cd5de7c577f26397d2` @ doc-86fb37ed00532831b8e67acb：While prompt injection and jailbreaking are related concepts in LLM security, they are often used interchangea …
    - `chunk-e8cc2b6834a2c530e2fcad10` @ doc-86fb37ed00532831b8e67acb：Prompt injection vulnerabilities are possible due to the nature of generative AI. Given the stochastic influen …
    - `chunk-ff8a87d0d88c14f7168efde2` @ doc-86fb37ed00532831b8e67acb：The severity and nature of the impact of a successful prompt injection attack can vary greatly and are largely …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=correct；引用=supported；拒答=not_applicable

### BQA-012｜术语及语义查询｜应作答｜变化：答案文本有变

- 问题：Derm7pt 是什么数据集？
- 预期：文档 ['paper:2606.15617']；要点 ['Derm7pt']
- 系统实际：作答（耗时 377.8 ms）
- 系统回答：检索到的原文直接证据： - “achieves the strongest overall results: 80.76% ACC / 60.00% F1 on Derm7pt and” [NeRD: Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded Chain-of-Thought in Medical Image Diagnosis · chunk-6ea63ce05320edcd881e0931]
- 引用（5 条）：
    - `chunk-6ea63ce05320edcd881e0931` @ doc-70c35c725fef8799991500f8：8 Hongxi Yang et al. achieves the strongest overall results: 80.76% ACC / 60.00% F1 on Derm7pt and 88.66% ACC  …
    - `chunk-522eb9d8deff2a4d6e345452` @ doc-70c35c725fef8799991500f8：fixed schema, we use GPT-5 Mini [14] to parse the predicted concepts and diagnosis from free-form text for eva …
    - `chunk-67f8da8439e4a735fa12d084` @ doc-70c35c725fef8799991500f8：pts within each group accordingly. Finally, we render the rationale with a fixed template: (i) report the sali …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-014｜术语及语义查询｜应作答｜变化：答案文本有变

- 问题：multi-agent 系统在哪些研究里被讨论？
- 预期：文档 ['paper:2609.28900']；要点 ['multi-agent']
- 系统实际：作答（耗时 441.7 ms）
- 系统回答：检索到的相关原文证据如下： - “strawman under realistic multi-agent deployment of model and context asymmetry.Section 6builds the key” [Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion · chunk-1656e6198f3d4eb7310cce90] - “teurs, Better Fixers: Scaling & Security in Linear Multi-Agent Workflows.arXiv preprint”  …
- 引用（5 条）：
    - `chunk-1656e6198f3d4eb7310cce90` @ doc-9b0ef853988d6ac1146ea020：capacity of the strawman under realistic multi-agent deployment of model and context asymmetry.Section 6builds …
    - `chunk-86f5cd3318bfb7da386309bd` @ doc-053c4681c135e61900b6d182：em Ozmen Garibay. Smarter Sabo- teurs, Better Fixers: Scaling & Security in Linear Multi-Agent Workflows.arXiv …
    - `chunk-588cced1264eec1b2b7b6151` @ doc-053c4681c135e61900b6d182：2505.22960. Binwei Yao, Chao Shang, Wanyu Du, Jianfeng He, Ruixue Lian, Yi Zhang, Hang Su, Sandesh Swamy, and  …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-015｜术语及语义查询｜应作答｜变化：答案文本有变

- 问题：AUROC 是什么指标？
- 预期：文档 ['paper:2609.29429']；要点 ['AUROC']
- 系统实际：作答（耗时 461.1 ms）
- 系统回答：检索到的原文直接证据： - “The AUROC advantage does” [Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures · chunk-44cd582860c79d6783e5fbed] - “Table 18:Kernel-View representation ablation on ACE.Pooled ACE-full AUROC under” [On the Effectiveness of Kernel-Level Evidence fo …
- 引用（5 条）：
    - `chunk-2c548b7cb0cbd3d90614329e` @ doc-38443598019e64691b4f66e4：ark baselines on the 38 usable benchmarks.Jev columns: generic NOUL AUROC and the targeted question selected s …
    - `chunk-44cd582860c79d6783e5fbed` @ doc-38443598019e64691b4f66e4：The AUROC advantage does not come from resolution. The scorer takes only 9 distinct values. Breaking its ties  …
    - `chunk-20a31f7b632b76ef56327c75` @ doc-8398b079e055c4456a001bee：Preprint Table 18:Kernel-View representation ablation on ACE.Pooled ACE-full AUROC under OWASP-groundedK=0on t …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-016｜术语及语义查询｜应作答｜变化：答案文本有变；引用有变

- 问题：PEFT 在基础模型上解决什么问题？
- 预期：文档 ['paper:2501.13787']；要点 ['Parameter-Efficient']
- 系统实际：作答（耗时 489.1 ms）
- 系统回答：根据检索到的原文证据： - “PEFT for Visual Content Generation Models subsection subsume the scope of the multi-modal model as” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-ae717b77f38375b526b5ba5f]
- 引用（5 条）：
    - `chunk-ae717b77f38375b526b5ba5f` @ doc-086c0557444be72ddfb3c0fd：g in mask) into prompts embedding as inputs to segment anything. diffusion model; B. LoRA tuning in diffusion  …
    - `chunk-af8916874a02a54f2547b2d4` @ doc-086c0557444be72ddfb3c0fd：ized by Multi-Modal Foundation Model (MFM) extends the ca- diversification and integration, as shown in Fig.1a …
    - `chunk-e78516a997d4da76b6632007` @ doc-086c0557444be72ddfb3c0fd：systems that can continuously learn new tasks while retaining In conclusion, the integration of PEFT with FMs  …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-017｜术语及语义查询｜应作答｜变化：答案文本有变

- 问题：OllamaDrama 中的 honeypot 部署在哪里？
- 预期：文档 ['paper:2609.29757']；要点 ['honeypot']
- 系统实际：作答（耗时 406.7 ms）
- 系统回答：根据检索到的原文证据： - “"OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Ex” [OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Exposed LLM Infrastructure · chunk-ada39a3d70fd203df933339d]
- 引用（6 条）：
    - `chunk-e7c4f5f3c7751a3ffa30b7ce` @ doc-e16f7d33561d58da8e56e445：full range of specialized LLM API endpoints. Our work aims to address this gap by introducing a dedicated hone …
    - `chunk-1c80f502e72fb42699eeb0ab` @ doc-e16f7d33561d58da8e56e445：OllamaDrama 5 2.4 Related Work In recent years, cyber deception has increasingly integrated LLMs to enhance ho …
    - `chunk-ada39a3d70fd203df933339d` @ doc-e16f7d33561d58da8e56e445：Springer Nature Singapore, Singapore (2027) 7.Karimi, A.: Galah: An LLM-powered web honeypot (2025),https://gi …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-019｜中英文混合查询｜应作答｜变化：答案文本有变

- 问题：DistillGuard 是做什么的？
- 预期：文档 ['paper:2609.28996']；要点 ['DistillGuard']
- 系统实际：作答（耗时 381.6 ms）
- 系统回答：检索到的原文直接证据： - “feature completeness and vulnerable to obfuscated malicious knowledge with lightweight LoRA fine-tuning, DistillGuard” [DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis via Static Graph and LLM Distillation · chunk-3e02e30d18b6d9d534a09cad]
- 引用（5 条）：
    - `chunk-1e26fb499bb6dbae04a358d4` @ doc-6848cfa4c508d3d98cbcc747：While online pedestal models possess superior secure in- static graph structure feature extraction, high-level …
    - `chunk-c58221ed9828a62061aaeec7` @ doc-6848cfa4c508d3d98cbcc747：strategies are further proposed to boost detection titatively characterize NPM attack patterns and summarize r …
    - `chunk-fef1ae1764a6dee6f3705bd6` @ doc-6848cfa4c508d3d98cbcc747：. make it a primary target for software supply chain attacks. To overcome these limitations, we propose Distil …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-020｜中英文混合查询｜应作答｜变化：答案文本有变

- 问题：OllamaDrama 蜜罐观察到了什么？
- 预期：文档 ['paper:2609.29757']；要点 ['OllamaDrama']
- 系统实际：作答（耗时 404.3 ms）
- 系统回答：根据检索到的原文证据： - “:Low-interactionhoneypots emulate a basic” [OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Exposed LLM Infrastructure · chunk-7e16e6ece9b5fa7bb906f527]
- 引用（6 条）：
    - `chunk-7e16e6ece9b5fa7bb906f527` @ doc-e16f7d33561d58da8e56e445：:Low-interactionhoneypots emulate a basic service skeleton,medium-interactionsystems provide partial functiona …
    - `chunk-2e3b3fec713324c33c3b0880` @ doc-e16f7d33561d58da8e56e445：62 requests specified the explicit string nonexistent, 44 referenced legitimate model names, and a single inst …
    - `chunk-f04f6a92012135f57321f790` @ doc-e16f7d33561d58da8e56e445：isrupting availability and driving up costs via Impact Context Overflow, Input resource exhaustion, token floo …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-021｜中英文混合查询｜应作答｜变化：答案文本有变

- 问题：Codetta 是什么？
- 预期：文档 ['paper:2609.28900']；要点 ['Codetta']
- 系统实际：作答（耗时 343.0 ms）
- 系统回答：检索到的原文直接证据： - “CODETTA: High-Capacity, Keyless, and Undetectable” [Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion · chunk-86ce9e6b5b0e6ce787a30993]
- 引用（6 条）：
    - `chunk-40710bf2b8e507ad4f7c387b` @ doc-9b0ef853988d6ac1146ea020：FINANCIAL IFEVAL CTF Method Qwen Llama Ministral Qwen Llama Ministral Qwen Llama Ministral Capacity (bits per  …
    - `chunk-1656e6198f3d4eb7310cce90` @ doc-9b0ef853988d6ac1146ea020：capacity of the strawman under realistic multi-agent deployment of model and context asymmetry.Section 6builds …
    - `chunk-e45c6b3a852060d4b6ed1edd` @ doc-9b0ef853988d6ac1146ea020：We analyze undetectability, the substitution channel, and correctness and soundness ofAlgorithm 2, following S …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable

### BQA-023｜中英文混合查询｜应作答｜变化：答案文本有变

- 问题：NeRD 是什么方法？
- 预期：文档 ['paper:2606.15617']；要点 ['NeRD']
- 系统实际：作答（耗时 363.0 ms）
- 系统回答：检索到的原文直接证据： - “Overall, NeRD demon” [NeRD: Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded Chain-of-Thought in Medical Image Diagnosis · chunk-675668ff34c9d9eeb7b36b4a]
- 引用（6 条）：
    - `chunk-675668ff34c9d9eeb7b36b4a` @ doc-70c35c725fef8799991500f8：tervened cases. Overall, NeRD demon- strates higher intervention-efficient refinement by enabling larger diagn …
    - `chunk-6ece9563486747c798438a8e` @ doc-70c35c725fef8799991500f8：r all items to obtain a mean score per method. Main Results.Fig. 3(b) summarizes the results of the human expe …
    - `chunk-5c71aaa24bd8d7056ac0313a` @ doc-70c35c725fef8799991500f8：NeRD 3 Fig.2: Framework of our method. Step 1: Induce a diagnostic rule set from concepts. Step 2: Execute Neu …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=correct；引用=partially_supported；拒答=not_applicable

### BQA-025｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它检测什么？
- 上文：user: DistillGuard 是做什么的？ / assistant: DistillGuard: Malicious NPM Package Detection
- 预期：文档 ['paper:2609.28996']；要点 ['DistillGuard']
- 系统实际：作答（耗时 479.6 ms）
- 系统回答：检索到的原文直接证据： - “that is difficult to detect using rule-based detection methods,” [DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis via Static Graph and LLM Distillation · chunk-1b8a5b3bb855e6ee7df0a863]
- 引用（5 条）：
    - `chunk-1b8a5b3bb855e6ee7df0a863` @ doc-6848cfa4c508d3d98cbcc747：igh-risk configuration characteristics as key evidence. that is difficult to detect using rule-based detection …
    - `chunk-b44b486d1caaf078ffbda922` @ doc-6848cfa4c508d3d98cbcc747：e the ‘package.json’ configuration file of each NPM package, grained function call graphs for each NPM package …
    - `chunk-0e71f6c4c71d2da9711d9d13` @ doc-6848cfa4c508d3d98cbcc747：ervative, placing the classification probability of a large This shows that dependency features help distingui …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect

### BQA-026｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它的研究对象是什么？
- 上文：user: Codetta 是什么？ / assistant: Codetta: High-Capacity, Keyless, and Undetectable Multi-Agen …
- 预期：文档 ['paper:2609.28900']；要点 ['Codetta']
- 系统实际：作答（耗时 427.9 ms）
- 系统回答：检索到的原文直接证据： - “CODETTA: High-Capacity, Keyless, and Undetectable” [Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion · chunk-86ce9e6b5b0e6ce787a30993]
- 引用（6 条）：
    - `chunk-40710bf2b8e507ad4f7c387b` @ doc-9b0ef853988d6ac1146ea020：FINANCIAL IFEVAL CTF Method Qwen Llama Ministral Qwen Llama Ministral Qwen Llama Ministral Capacity (bits per  …
    - `chunk-1656e6198f3d4eb7310cce90` @ doc-9b0ef853988d6ac1146ea020：capacity of the strawman under realistic multi-agent deployment of model and context asymmetry.Section 6builds …
    - `chunk-e45c6b3a852060d4b6ed1edd` @ doc-9b0ef853988d6ac1146ea020：We analyze undetectability, the substitution channel, and correctness and soundness ofAlgorithm 2, following S …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect

### BQA-028｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它用在哪个领域？
- 上文：user: NeRD 是什么方法？ / assistant: NeRD: Neuro-Symbolic Rule Distillation
- 预期：文档 ['paper:2606.15617']；要点 ['NeRD']
- 系统实际：作答（耗时 437.7 ms）
- 系统回答：检索到的原文直接证据： - “Overall, NeRD demon” [NeRD: Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded Chain-of-Thought in Medical Image Diagnosis · chunk-675668ff34c9d9eeb7b36b4a]
- 引用（6 条）：
    - `chunk-675668ff34c9d9eeb7b36b4a` @ doc-70c35c725fef8799991500f8：tervened cases. Overall, NeRD demon- strates higher intervention-efficient refinement by enabling larger diagn …
    - `chunk-6ece9563486747c798438a8e` @ doc-70c35c725fef8799991500f8：r all items to obtain a mean score per method. Main Results.Fig. 3(b) summarizes the results of the human expe …
    - `chunk-5c71aaa24bd8d7056ac0313a` @ doc-70c35c725fef8799991500f8：NeRD 3 Fig.2: Framework of our method. Step 1: Induce a diagnostic rule set from concepts. Step 2: Execute Neu …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect

### BQA-029｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它提出的方法叫什么？
- 上文：user: SAGE 这篇论文的方法名称是什么？ / assistant: SAGE: Mitigating Long-Horizon Reasoning Biases via Topologic …
- 预期：文档 ['paper:2609.30192']；要点 ['SAGE']
- 系统实际：作答（耗时 591.0 ms）
- 系统回答：检索到的原文直接证据： - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance · chunk-5c35e2d194d9c97348a5e958]
- 引用（5 条）：
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
    - `chunk-03317ba315f16be669e3c769` @ doc-52378c1633f50c6eb3b600e4：soning as a stress test for exploration and compounding biases. Section 5.4 is the ablation study of the two c …
    - `chunk-9a6ae6087bfe15b36556ced3` @ doc-52378c1633f50c6eb3b600e4：ΨSAGE(τ)−sup τ∈G ΨSAGE(τ)≥∆ , thenPEBM(G)/P EBM(F)≤e −λ∆ πθold(G)/π θold(F). Thus, increasingλ exponentially s …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect

### BQA-030｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它拦截的是哪一类执行？
- 上文：user: Hard Stop 论文关注什么？ / assistant: Hard Stop: Kernel-Level Preemption and Containment for Rogue …
- 预期：文档 ['paper:2609.29808']；要点 ['Hard Stop']
- 系统实际：作答（耗时 557.8 ms）
- 系统回答：根据检索到的原文证据： - “Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint” [Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution · chunk-9aa9b7f0bfc461185e805840]
- 引用（5 条）：
    - `chunk-9aa9b7f0bfc461185e805840` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint # 2. Template Injection & Traversal  …
    - `chunk-40e6485386bfdf62a9f37df0` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint } exceptException: pass returnNone d …
    - `chunk-dd6697dfa7ef5bd2eb0080ec` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint defterminate_process_group(self)->bo …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect

### BQA-039｜真实多跳问答｜应拒答｜变化：引用有变

- 问题：CISA KEV 收录的漏洞中，哪些同时在我们采集的论文正文里被讨论？
- 系统实际：作答（耗时 702.1 ms）
- 系统回答：CVE-2025-62593：Ray-Project Ray contains a code injection vulnerability that could allow remote code execution. Developers using Ray as a development tool may be exposed to this vulnerability exploitable through Firefox and Safari. CVE-2026-9198：Langflow contains a code injection vulnerability that allows unauthenticate …
- 引用（5 条）：
    - `chunk-a7fda3d62674c6d15a012d7a` @ doc-8398b079e055c4456a001bee：c applications (OWASP Gen AI Security Project, 2026). Past compromises of comparable delivery channels (npm In …
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-de5719233bb413351f90a2da` @ doc-f0f2afa26abdac092e478e6a：ttachments, or namespace configurations through legitimate kernel interfaces without exploiting a kernel vulne …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（suggested，medium）—— 应拒答却作答，失败分类 candidate_multihop_answered_topically（规则明确）
- 改造前人工标签：答案=（空）；引用=unknown；拒答=incorrect

### BQA-040｜真实多跳问答｜应拒答｜变化：答案文本有变；引用有变

- 问题：OllamaDrama 蜜罐观察到的攻击，与已知在野利用漏洞清单中的哪些条目对应？
- 系统实际：作答（耗时 733.9 ms）
- 系统回答：检索到的相关原文证据如下： - “Table 5: Summary & MITRE ATLAS Mapping of Observed Attack Behaviors” [OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Exposed LLM Infrastructure · chunk-f7fd040bcb32d7e198348cbe] - “OllamaDrama: Designing and Deploying a” [OllamaDrama: Designing and Deploying a Honeypot to Measure …
- 引用（5 条）：
    - `chunk-f79cb023919171692bfdb65c` @ doc-e16f7d33561d58da8e56e445：H architectural design including the core components alongside the two expected attack categories we intend to …
    - `chunk-791a99218eb26e365aa244e1` @ doc-e16f7d33561d58da8e56e445：18 K. Elzer et al.. Unfortunately, we’ve discovered a flaw in your system & found our way in Make a donation t …
    - `chunk-f7fd040bcb32d7e198348cbe` @ doc-e16f7d33561d58da8e56e445：OllamaDrama 17 Table 5: Summary & MITRE ATLAS Mapping of Observed Attack Behaviors ATLAS Observed Behaviors De …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（suggested，medium）—— 应拒答却作答，失败分类 candidate_multihop_answered_topically（规则明确）
- 改造前人工标签：答案=（空）；引用=partially_supported；拒答=incorrect

### BQA-044｜无证据问题与范围外问题｜应拒答｜变化：答案文本有变

- 问题：2027 年世界杯冠军是谁？
- 系统实际：作答（耗时 421.9 ms）
- 系统回答：根据检索到的原文证据： - “Under review as a conference paper at ICLR 2027” [Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures · chunk-c31fcd3b34fc78bab9f78cd5] - “Springer Nature Singapore, Singapore (2027)” [OllamaDrama: Designing and Deploying a Honeypot to Measure At …
- 引用（5 条）：
    - `chunk-d86f26ed40a6d58a18458899` @ doc-e16f7d33561d58da8e56e445：0.1109/EuroSP68448.2026.00063 4.Catledge, L.D., Pitkow, J.E.: Characterizing browsing strategies in the World- …
    - `chunk-c31fcd3b34fc78bab9f78cd5` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 Nicholas Goldowsky-Dill, Bilal Chughtai, Stefan Heimersheim, a …
    - `chunk-95086229c3eb626cfb833a43` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 Yupei Liu, Yuqi Jia, Jinyuan Jia, Dawn Song, and Neil Zhenqian …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（suggested，medium）—— 应拒答却作答，失败分类 numeric_token_false_positive（规则明确）
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect

### BQA-047｜拒答及证据不足｜应拒答｜变化：答案文本有变

- 问题：请总结全部 22 份文档的主要结论
- 系统实际：作答（耗时 473.6 ms）
- 系统回答：根据检索到的原文证据： - “ΨP(r t,Sj) =∥P Sjrt∥22∥r t∥22 +ε , (4)” [SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance · chunk-cf530a338ae66b8a214ee727] - “search?query=product%3A%22ollama%22” [OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Exposed LLM Infrastructure · chunk-ebc2ddc7ee4b …
- 引用（5 条）：
    - `chunk-ebc2ddc7ee4bb700d216d628` @ doc-e16f7d33561d58da8e56e445：22 K. Elzer et al.. 15.NIST: CVE-2025-63389. (Missing Authentication for Critical Function) (2025), https://nv …
    - `chunk-cf530a338ae66b8a214ee727` @ doc-52378c1633f50c6eb3b600e4：spaceS j: ΨP(r t,Sj) =∥P Sjrt∥22∥r t∥22 +ε , (4) where PSj projects onto Sj. Larger ΨP indicates the operator  …
    - `chunk-ebe17bce2bf3c43a07bfae05` @ doc-9b0ef853988d6ac1146ea020：hable from a uniform vector over Zq, so each of its coefficients can be handed to the carrier as a uniform q-a …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（suggested，medium）—— 应拒答却作答，失败分类 synthesis_request_answered_with_quotes（规则明确）
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect

### BQA-048｜拒答及证据不足｜应拒答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：那篇论文的实验结果是多少？
- 系统实际：作答（耗时 517.7 ms）
- 系统回答：根据检索到的原文证据： - “Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.05530, 2024.” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-a785e777ad83e7d8cb364c69] - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-H …
- 引用（4 条）：
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（pending_human_review，low）—— 应拒答却作答，失败分类 other；该题期望行为本身存在口径分歧，需人工裁定
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=correct

### BQA-049｜拒答及证据不足｜应拒答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：TrustedGuard 的量子纠缠检测机制是什么？
- 系统实际：作答（耗时 548.5 ms）
- 系统回答：检索到的原文直接证据： - “Numbers identify selected zero-based monitor decisions; scaffold events are unnumbered.” [Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure · chunk-f7bbefb749c256b5be855e69] - “that is difficult to detect using rule-based detection methods,” [DistillGuard: Malicious NPM Package Detection  …
- 引用（6 条）：
    - `chunk-09a241a5b89750429119b0dc` @ doc-56f791348270a7a71d56fc43：index using the literal protected path. BLOCK 97 Agent action: reconstruct the path from direct character code …
    - `chunk-b44b486d1caaf078ffbda922` @ doc-6848cfa4c508d3d98cbcc747：e the ‘package.json’ configuration file of each NPM package, grained function call graphs for each NPM package …
    - `chunk-f7bbefb749c256b5be855e69` @ doc-56f791348270a7a71d56fc43：tion. Numbers identify selected zero-based monitor decisions; scaffold events are unnumbered. Task, policy, an …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（pending_human_review，low）—— 应拒答却作答，失败分类 other；该题期望行为本身存在口径分歧，需人工裁定
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=correct

## 三、争议口径与拒答行为翻转的题（详版）

### BQA-025｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它检测什么？
- 上文：user: DistillGuard 是做什么的？ / assistant: DistillGuard: Malicious NPM Package Detection
- 预期：文档 ['paper:2609.28996']；要点 ['DistillGuard']
- 系统实际：作答（耗时 479.6 ms）
- 系统回答：检索到的原文直接证据： - “that is difficult to detect using rule-based detection methods,” [DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis via Static Graph and LLM Distillation · chunk-1b8a5b3bb855e6ee7df0a863]
- 引用（5 条）：
    - `chunk-1b8a5b3bb855e6ee7df0a863` @ doc-6848cfa4c508d3d98cbcc747：igh-risk configuration characteristics as key evidence. that is difficult to detect using rule-based detection …
    - `chunk-b44b486d1caaf078ffbda922` @ doc-6848cfa4c508d3d98cbcc747：e the ‘package.json’ configuration file of each NPM package, grained function call graphs for each NPM package …
    - `chunk-0e71f6c4c71d2da9711d9d13` @ doc-6848cfa4c508d3d98cbcc747：ervative, placing the classification probability of a large This shows that dependency features help distingui …
    - `chunk-4ba04b752c48e90dbd6e5dd0` @ doc-6848cfa4c508d3d98cbcc747：Software supply chain security primarily concerns mali- node-ipc attack incident. Container registries like Do …
    - `chunk-2343ec5b76e716d790e4758d` @ doc-6848cfa4c508d3d98cbcc747：tively balanced performance between precision and re- and evaluation metrics, with only one static analysis br …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect
- 机器建议的待确认项：无
- 缺失证据/判据：引用内容是否支持答案中的结论需人工判断（引用可追溯 ≠ 引用支持结论）
- 需要人决定：应回答

### BQA-026｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它的研究对象是什么？
- 上文：user: Codetta 是什么？ / assistant: Codetta: High-Capacity, Keyless, and Undetectable Multi-Agen …
- 预期：文档 ['paper:2609.28900']；要点 ['Codetta']
- 系统实际：作答（耗时 427.9 ms）
- 系统回答：检索到的原文直接证据： - “CODETTA: High-Capacity, Keyless, and Undetectable” [Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion · chunk-86ce9e6b5b0e6ce787a30993]
- 引用（6 条）：
    - `chunk-40710bf2b8e507ad4f7c387b` @ doc-9b0ef853988d6ac1146ea020：FINANCIAL IFEVAL CTF Method Qwen Llama Ministral Qwen Llama Ministral Qwen Llama Ministral Capacity (bits per  …
    - `chunk-1656e6198f3d4eb7310cce90` @ doc-9b0ef853988d6ac1146ea020：capacity of the strawman under realistic multi-agent deployment of model and context asymmetry.Section 6builds …
    - `chunk-e45c6b3a852060d4b6ed1edd` @ doc-9b0ef853988d6ac1146ea020：We analyze undetectability, the substitution channel, and correctness and soundness ofAlgorithm 2, following S …
    - `chunk-86ce9e6b5b0e6ce787a30993` @ doc-9b0ef853988d6ac1146ea020：CODETTA: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion Qi Pang Virginia Smith Wenting Zheng C …
    - `chunk-ebe17bce2bf3c43a07bfae05` @ doc-9b0ef853988d6ac1146ea020：hable from a uniform vector over Zq, so each of its coefficients can be handed to the carrier as a uniform q-a …
    - `chunk-ee4b3e79d54da71275cae71a` @ doc-9b0ef853988d6ac1146ea020：tions” can be posed for any number of answers, so the alphabet may change from token to token. “Questions” can …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect
- 机器建议的待确认项：无
- 缺失证据/判据：引用内容是否支持答案中的结论需人工判断（引用可追溯 ≠ 引用支持结论）
- 需要人决定：应回答

### BQA-028｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它用在哪个领域？
- 上文：user: NeRD 是什么方法？ / assistant: NeRD: Neuro-Symbolic Rule Distillation
- 预期：文档 ['paper:2606.15617']；要点 ['NeRD']
- 系统实际：作答（耗时 437.7 ms）
- 系统回答：检索到的原文直接证据： - “Overall, NeRD demon” [NeRD: Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded Chain-of-Thought in Medical Image Diagnosis · chunk-675668ff34c9d9eeb7b36b4a]
- 引用（6 条）：
    - `chunk-675668ff34c9d9eeb7b36b4a` @ doc-70c35c725fef8799991500f8：tervened cases. Overall, NeRD demon- strates higher intervention-efficient refinement by enabling larger diagn …
    - `chunk-6ece9563486747c798438a8e` @ doc-70c35c725fef8799991500f8：r all items to obtain a mean score per method. Main Results.Fig. 3(b) summarizes the results of the human expe …
    - `chunk-5c71aaa24bd8d7056ac0313a` @ doc-70c35c725fef8799991500f8：NeRD 3 Fig.2: Framework of our method. Step 1: Induce a diagnostic rule set from concepts. Step 2: Execute Neu …
    - `chunk-4be51f4b81e36bbffa7fb8de` @ doc-70c35c725fef8799991500f8：NeRD 7 Fig.4: NeRD generated MCoTs. Table 2: Average concept count. Pos Table 3: Intervention results on Derm7 …
    - `chunk-a7874d53d8db6974b188f298` @ doc-70c35c725fef8799991500f8：s for reaching correct conclusions without image access. 3.3 Experiment 2: Fine-Tuned MLLMs for Interpretable  …
    - `chunk-522eb9d8deff2a4d6e345452` @ doc-70c35c725fef8799991500f8：fixed schema, we use GPT-5 Mini [14] to parse the predicted concepts and diagnosis from free-form text for eva …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（6 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect
- 机器建议的待确认项：无
- 缺失证据/判据：引用内容是否支持答案中的结论需人工判断（引用可追溯 ≠ 引用支持结论）
- 需要人决定：应回答

### BQA-029｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它提出的方法叫什么？
- 上文：user: SAGE 这篇论文的方法名称是什么？ / assistant: SAGE: Mitigating Long-Horizon Reasoning Biases via Topologic …
- 预期：文档 ['paper:2609.30192']；要点 ['SAGE']
- 系统实际：作答（耗时 591.0 ms）
- 系统回答：检索到的原文直接证据： - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance · chunk-5c35e2d194d9c97348a5e958]
- 引用（5 条）：
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
    - `chunk-03317ba315f16be669e3c769` @ doc-52378c1633f50c6eb3b600e4：soning as a stress test for exploration and compounding biases. Section 5.4 is the ablation study of the two c …
    - `chunk-9a6ae6087bfe15b36556ced3` @ doc-52378c1633f50c6eb3b600e4：ΨSAGE(τ)−sup τ∈G ΨSAGE(τ)≥∆ , thenPEBM(G)/P EBM(F)≤e −λ∆ πθold(G)/π θold(F). Thus, increasingλ exponentially s …
    - `chunk-4b72fc8fa621782e6f526842` @ doc-52378c1633f50c6eb3b600e4：NeurIPS Paper Checklist 1.Claims Question: Do the main claims made in the abstract and introduction accurately …
    - `chunk-f6292119dac456a957c56f50` @ doc-52378c1633f50c6eb3b600e4：com/datasets has curated licenses for some datasets. Their licensing guide can help determine the license of a …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect
- 机器建议的待确认项：无
- 缺失证据/判据：引用内容是否支持答案中的结论需人工判断（引用可追溯 ≠ 引用支持结论）
- 需要人决定：应回答

### BQA-030｜多轮追问｜应作答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：它拦截的是哪一类执行？
- 上文：user: Hard Stop 论文关注什么？ / assistant: Hard Stop: Kernel-Level Preemption and Containment for Rogue …
- 预期：文档 ['paper:2609.29808']；要点 ['Hard Stop']
- 系统实际：作答（耗时 557.8 ms）
- 系统回答：根据检索到的原文证据： - “Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint” [Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution · chunk-9aa9b7f0bfc461185e805840]
- 引用（5 条）：
    - `chunk-9aa9b7f0bfc461185e805840` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint # 2. Template Injection & Traversal  …
    - `chunk-40e6485386bfdf62a9f37df0` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint } exceptException: pass returnNone d …
    - `chunk-dd6697dfa7ef5bd2eb0080ec` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint defterminate_process_group(self)->bo …
    - `chunk-6b9546662a106a418714e03e` @ doc-f0f2afa26abdac092e478e6a：=========== Platform: AMD Zen 5 (Kern), Linux 6.11 PREEMPT_DYNAMIC, Python 3.14 Reference: Kalibera & Jones (2 …
    - `chunk-f9d26319bd709c7eebf87b3b` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint Security & Concurrency Mechanism / L …
- 机器建议（B 类）·答案正确性：**correct**（suggested，medium）—— 预期文档被引用命中（5 条引用）且预期要点逐字出现在答案中；机器核对，仍需人工确认完整性与是否答非所问
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=incorrect
- 机器建议的待确认项：无
- 缺失证据/判据：引用内容是否支持答案中的结论需人工判断（引用可追溯 ≠ 引用支持结论）
- 需要人决定：应回答

### BQA-031｜跨文档问答｜应作答｜变化：答案文本有变

- 问题：AUROC 在哪些文档中被讨论？
- 预期：文档 ['paper:2609.28915', 'paper:2609.29429']；要点 ['AUROC']
- 系统实际：作答（耗时 438.4 ms）
- 系统回答：检索到的相关原文证据如下： - “The AUROC advantage does” [Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures · chunk-44cd582860c79d6783e5fbed] - “Table 18:Kernel-View representation ablation on ACE.Pooled ACE-full AUROC under” [On the Effectiveness of Kernel-Level Evidence for Agent Security · chunk-20a31f7b632b76ef56327c75] - “AUROC and the targeted question selected split-half.” [Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures · chunk-2c548b7cb0cbd3d90614329e] - “TF-IDF LR: out-of-fold AUROC (SD over 3” [Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot De …
- 引用（5 条）：
    - `chunk-2c548b7cb0cbd3d90614329e` @ doc-38443598019e64691b4f66e4：ark baselines on the 38 usable benchmarks.Jev columns: generic NOUL AUROC and the targeted question selected s …
    - `chunk-44cd582860c79d6783e5fbed` @ doc-38443598019e64691b4f66e4：The AUROC advantage does not come from resolution. The scorer takes only 9 distinct values. Breaking its ties  …
    - `chunk-20a31f7b632b76ef56327c75` @ doc-8398b079e055c4456a001bee：Preprint Table 18:Kernel-View representation ablation on ACE.Pooled ACE-full AUROC under OWASP-groundedK=0on t …
    - `chunk-ddc8ff128228b8a2c57cf5cb` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 Figure 5:Reference gain against baseline AUROC.Pairs with lowe …
    - `chunk-b6e12a610c133c01a06e9ac8` @ doc-8398b079e055c4456a001bee：90 session/fold evaluations. With OWASP gro
- 机器建议（B 类）·答案正确性：**partial**（pending_human_review，low）—— 多来源被引用但未证明跨来源信息整合（输出为并列摘录）；按统一口径「跨文档综合」答案正确性最多判 partial，需人工确认
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable
- 机器建议的待确认项：跨文档「是否真正综合」缺少判定标准
- 缺失证据/判据：缺少『多文档引用是否算综合』的判定标准；系统输出无跨来源推理表述
- 需要人决定：应回答

### BQA-032｜跨文档问答｜应作答｜变化：答案文本有变

- 问题：kernel-level 在哪些文档中出现？
- 预期：文档 ['paper:2609.28915', 'paper:2609.29808']；要点 ['kernel-level']
- 系统实际：作答（耗时 423.8 ms）
- 系统回答：检索到的相关原文证据如下： - “Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint” [Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution · chunk-7c6fdba1430ff6e44db50349] - “Hard Stop: Kernel-Level Preemptio” [Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution · chunk-9aa9b7f0bfc461185e805840] - “transformations, while kernel-level eBPF LSM interception achieves 100% detection accuracy.” [Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution · chunk-7c6fdba1430ff6e44db50349] - “The supervisor issues a kernel-level SIGKILL to the target process” [Hard Stop: Kernel-Level Preemption and Containment for Rogue …
- 引用（6 条）：
    - `chunk-7c6fdba1430ff6e44db50349` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint 7.4 Empirical Validation Protocols & …
    - `chunk-dce559be9fb9fbb750a526c5` @ doc-8398b079e055c4456a001bee：. . . . . . . . . . . . . . . 26 E.9 Safety perimeter . . . . . . . . . . . . . . . . . . . . . . . . . . . .  …
    - `chunk-5a7e7933367ec788cb6a0079` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemption for Rogue Agentic Execution A Preprint Boundary conditions: The TCB exclude …
    - `chunk-834172ea6722a03c4a60627e` @ doc-8398b079e055c4456a001bee：Preprint ON THEEFFECTIVENESS OFKERNEL-LEVEL EVIDENCE FORAGENTSECURITY Spencer King1 Zhilu Zhang2 Mikhail Kuzne …
    - `chunk-ff969be40008a83dde076597` @ doc-f0f2afa26abdac092e478e6a：and isolates the container with zero tokens leaked. 7.2 Out-of-Band POSIX Supervisor & Production Orchestrator …
    - `chunk-9aa9b7f0bfc461185e805840` @ doc-f0f2afa26abdac092e478e6a：Hard Stop: Kernel-Level Preemptio
- 机器建议（B 类）·答案正确性：**partial**（pending_human_review，low）—— 多来源被引用但未证明跨来源信息整合（输出为并列摘录）；按统一口径「跨文档综合」答案正确性最多判 partial，需人工确认
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable
- 机器建议的待确认项：跨文档「是否真正综合」缺少判定标准
- 缺失证据/判据：缺少『多文档引用是否算综合』的判定标准；系统输出无跨来源推理表述
- 需要人决定：应回答

### BQA-034｜跨文档问答｜应作答｜变化：答案文本有变；引用有变

- 问题：multi-agent 主题出现在哪些论文中？
- 预期：文档 ['paper:2609.28900', 'paper:2609.30028']；要点 ['multi-agent']
- 系统实际：作答（耗时 492.2 ms）
- 系统回答：检索到的相关原文证据如下： - “Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.05530, 2024.” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-a785e777ad83e7d8cb364c69] - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance · chunk-5c35e2d194d9c97348a5e958] - “Under review as a conference paper at ICLR 2027” [Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures · chunk-22ab00d3565127a063fbfb1b] - “arXiv preprint arXiv:2503.11926, 2025.” [Just Ask Jev: Reinforcement Learning for Calibrated D …
- 引用（4 条）：
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
    - `chunk-1c81026ab5a957ec178913c4` @ doc-086c0557444be72ddfb3c0fd：[32]Y. Xin, S. Luo, H. Zhou, J. Du, X. Liu, Y. Fan, B. Ommer, “High-resolution image synthesis with latent Q.  …
- 机器建议（B 类）·答案正确性：**unknown**（pending_human_review，low）—— 有引用但未命中预期文档/要点；引用内容是否等价于题目要求需人工判断
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable
- 机器建议的待确认项：跨文档「是否真正综合」缺少判定标准
- 缺失证据/判据：缺少『多文档引用是否算综合』的判定标准；系统输出无跨来源推理表述
- 需要人决定：应回答

### BQA-038｜跨文档问答｜应作答｜变化：引用有变

- 问题：reinforcement learning 出现在哪些论文里？
- 预期：文档 ['paper:2609.29230', 'paper:2609.29429']；要点 ['Reinforcement']
- 系统实际：作答（耗时 475.2 ms）
- 系统回答：OPENALEX-W7214342592：End-to-end event extraction remains challenging for large language models as it requires simultaneous identification of event triggers, classification of event types, and extraction of schema-grounded argument spans. We present EAGER, a reinforcement learning framework for generative event extraction that combines fine-grained verifiable rewards with Schema-Contrastive Advantage Estimation to alle… OPENALEX-W7214329963：Detectors of alignment failures screen deployed language models and score alignment benchmarks. Most are generative judges that spend a decoding pass on every criterion, and classifiers that read token probabilities, such as Llama Guard, still score one fi …
- 引用（6 条）：
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-c31fcd3b34fc78bab9f78cd5` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 Nicholas Goldowsky-Dill, Bilal Chughtai, Stefan Heimersheim, a …
    - `chunk-d30e94203b39a1514571f2c3` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 Jiayi Ye, Yanbo Wang, Yue Huang, Dongping Chen, Qihui Zhang, N …
    - `chunk-15641d6a59af6d328b210e81` @ doc-38443598019e64691b4f66e4：87, 2017. URLhttps://proceedings.neurips.cc/paper/2017/hash/ 4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html. G …
    - `chunk-f16db047c8ac29168019d5a8` @ doc-38443598019e64691b4f66e4：orum?id= XccDXrDNLek. Curtis G. Northcutt, Lu Jiang, and Isaac L. Chuang. Confident learning: Estimating uncer …
    - `chunk-31b03a034fbd206e71ea50dc` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 Neil Kale, Chen Bo Calvin Zhang, Kevin Zhu, Ankit Aich, Paula  …
- 机器建议（B 类）·答案正确性：**partial**（pending_human_review，low）—— 多来源被引用但未证明跨来源信息整合（输出为并列摘录）；按统一口径「跨文档综合」答案正确性最多判 partial，需人工确认
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**correct**（suggested，medium）—— 该题应作答，系统未拒答
- 改造前人工标签：答案=partial；引用=partially_supported；拒答=not_applicable
- 机器建议的待确认项：跨文档「是否真正综合」缺少判定标准
- 缺失证据/判据：缺少『多文档引用是否算综合』的判定标准；系统输出无跨来源推理表述
- 需要人决定：应回答

### BQA-048｜拒答及证据不足｜应拒答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：那篇论文的实验结果是多少？
- 系统实际：作答（耗时 517.7 ms）
- 系统回答：根据检索到的原文证据： - “Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.05530, 2024.” [Parameter-Efficient Fine-Tuning for Foundation Models · chunk-a785e777ad83e7d8cb364c69] - “Question: Does the paper describe potential risks incurred by study participants, whether” [SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance · chunk-5c35e2d194d9c97348a5e958] - “Under review as a conference paper at ICLR 2027” [Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures · chunk-22ab00d3565127a063fbfb1b]
- 引用（4 条）：
    - `chunk-22ab00d3565127a063fbfb1b` @ doc-38443598019e64691b4f66e4：Under review as a conference paper at ICLR 2027 the risks of promoting obfuscation. arXiv preprint arXiv:2503. …
    - `chunk-a785e777ad83e7d8cb364c69` @ doc-086c0557444be72ddfb3c0fd：ons of tokens of J. Z. Pan, “An empirical study on parameter-efficient context,” arXiv preprint arXiv:2403.055 …
    - `chunk-5c35e2d194d9c97348a5e958` @ doc-52378c1633f50c6eb3b600e4：15. Institutional review board (IRB) approvals or equivalent for research with human subjects Question: Does t …
    - `chunk-1c81026ab5a957ec178913c4` @ doc-086c0557444be72ddfb3c0fd：[32]Y. Xin, S. Luo, H. Zhou, J. Du, X. Liu, Y. Fan, B. Ommer, “High-resolution image synthesis with latent Q.  …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（pending_human_review，low）—— 应拒答却作答，失败分类 other；该题期望行为本身存在口径分歧，需人工裁定
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=correct
- 机器建议的待确认项：无
- 缺失证据/判据：需人工按拒答规则确认该题是否确属证据不足
- 需要人决定：应拒答

### BQA-049｜拒答及证据不足｜应拒答｜变化：答案文本有变；引用有变；拒答行为翻转（旧=拒答 → 新=作答）

- 问题：TrustedGuard 的量子纠缠检测机制是什么？
- 系统实际：作答（耗时 548.5 ms）
- 系统回答：检索到的原文直接证据： - “Numbers identify selected zero-based monitor decisions; scaffold events are unnumbered.” [Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure · chunk-f7bbefb749c256b5be855e69] - “that is difficult to detect using rule-based detection methods,” [DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis via Static Graph and LLM Distillation · chunk-b44b486d1caaf078ffbda922] - “A company includes an instruction in a job description to identify AI-generated applications.” [owasp_genai · chunk-aa451b81dc451eca17354fc3]
- 引用（6 条）：
    - `chunk-09a241a5b89750429119b0dc` @ doc-56f791348270a7a71d56fc43：index using the literal protected path. BLOCK 97 Agent action: reconstruct the path from direct character code …
    - `chunk-b44b486d1caaf078ffbda922` @ doc-6848cfa4c508d3d98cbcc747：e the ‘package.json’ configuration file of each NPM package, grained function call graphs for each NPM package …
    - `chunk-f7bbefb749c256b5be855e69` @ doc-56f791348270a7a71d56fc43：tion. Numbers identify selected zero-based monitor decisions; scaffold events are unnumbered. Task, policy, an …
    - `chunk-1b8a5b3bb855e6ee7df0a863` @ doc-6848cfa4c508d3d98cbcc747：igh-risk configuration characteristics as key evidence. that is difficult to detect using rule-based detection …
    - `chunk-aa451b81dc451eca17354fc3` @ doc-86fb37ed00532831b8e67acb：A company includes an instruction in a job description to identify AI-generated applications. An applicant, un …
    - `chunk-195ce6e446d71206ccae9a9b` @ doc-56f791348270a7a71d56fc43：ut prior tool-call history, it allows all eight writes and subsequently allows execution of the assembled prog …
- 机器建议（B 类）·答案正确性：**not_applicable**（suggested，high）—— 该题期望拒答，答案正确性维度不适用
- 机器建议（B 类）·引用支持性：**unknown**（pending_human_review，low）—— 引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，无法用引用核验其结论
- 机器建议（B 类）·拒答正确性：**incorrect**（pending_human_review，low）—— 应拒答却作答，失败分类 other；该题期望行为本身存在口径分歧，需人工裁定
- 改造前人工标签：答案=（空）；引用=not_applicable；拒答=correct
- 机器建议的待确认项：无
- 缺失证据/判据：需人工按拒答规则确认该题是否确属证据不足
- 需要人决定：应拒答

