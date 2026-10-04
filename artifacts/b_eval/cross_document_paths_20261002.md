# 跨文档多跳路径复核材料（2026-10-02 批次）

来源：`artifacts/b_eval/multihop_path_validation_20261002_v2.json`（跨文档 10/21 连通）。
每条路径都列出**节点 / 边 / evidence ID / 可回读 quote**；未连通的题保留原样。

## 一、新增来源（8 篇）

| arXiv ID | 标题 | 命中目标文档 | 文档间边 | 术语边 |
| --- | --- | --- | --- | --- |
| 2609.03999 | Shifting from Injection to Interaction: Rethinking Web Security in the | source:nist_ai_rmf, source:owasp_genai | 2 | 17 |
| 2609.22961 | When Agentic Trust Crosses Organizational Boundaries: Structural Exter | official:eu_ai_act, source:owasp_genai | 2 | 8 |
| 2609.35266 | Continuous Assurance of Agentic Security Auditors for Software Deliver | official:eu_ai_act, source:nist_ai_rmf | 2 | 6 |
| 2609.24016 | Context-Aware Pre-Deployment Evaluation of AI Systems: A Regulatory Fr | official:eu_ai_act, source:nist_ai_rmf | 2 | 5 |
| 2608.10530 | On Understanding, Identifying, and Mitigating Vulnerabilities in Agent | source:owasp_genai | 1 | 16 |
| 2608.28327 | Layered LLM Defenses as an Ensemble: Access Tiers, Inference Cost, and | source:owasp_genai | 1 | 13 |
| 2609.23894 | Connecting the Dots in Agentic AI Security: A Cross-Dimensional Threat | source:owasp_genai | 1 | 12 |
| 2609.22882 | The Law of Stop: Interruptibility, Injunctions, and the Governance of  | official:eu_ai_act | 1 | 8 |

## 二、已连通路径（10 条）

### BMH-014｜reinforcement learning 出现在哪些论文中？

- 节点：term:reinforcement learning → doc:paper:2609.22882 → doc:official:eu_ai_act
- 边：`term:reinforcement learning` --mentioned_in--> `doc:paper:2609.22882`
- 边：`doc:paper:2609.22882` --cites--> `doc:official:eu_ai_act`
- evidence `chunk-e1ef2bd6c0ae27c4de3d048c` [287:309] quote='reinforcement learning' 回读=OK （term:reinforcement learning → doc:paper:2609.22882）
    - 上下文：…reward hacking was found and an April freeze of production reinforcement learning environments, neither disclosed at the time; the same docum…
- evidence `chunk-f9d6b23e1fa81a89b80710c3` [731:758] quote='Artificial Intelligence Act' 回读=OK （paper:2609.22882 → official:eu_ai_act）
    - 上下文：…LYSIS (Malgieri et al. eds., forthcoming 2026); Lena Enqvist, ‘Human Oversight’ in the EU Artificial Intelligence Act: What, When and by Whom?, 15 LAW, INNOVATION & TECH. 508 (2023); Ben Green, The Flaws of…
- 与候选声明链路一致：False

### BMH-016｜supply chain 出现在哪些文档中？

- 节点：term:supply chain → doc:paper:2609.22882 → doc:official:eu_ai_act
- 边：`term:supply chain` --mentioned_in--> `doc:paper:2609.22882`
- 边：`doc:paper:2609.22882` --cites--> `doc:official:eu_ai_act`
- evidence `chunk-d478e74245fd42a48c9e97c0` [607:619] quote='supply chain' 回读=OK （term:supply chain → doc:paper:2609.22882）
    - 上下文：…hysical accident; at larger scale it can disrupt markets or supply chains; and, in the extreme case of a capable and misaligned syst…
- evidence `chunk-f9d6b23e1fa81a89b80710c3` [731:758] quote='Artificial Intelligence Act' 回读=OK （paper:2609.22882 → official:eu_ai_act）
    - 上下文：…LYSIS (Malgieri et al. eds., forthcoming 2026); Lena Enqvist, ‘Human Oversight’ in the EU Artificial Intelligence Act: What, When and by Whom?, 15 LAW, INNOVATION & TECH. 508 (2023); Ben Green, The Flaws of…
- 与候选声明链路一致：False

### BMH-017｜risk management 出现在哪些文档中？

- 节点：term:risk management → doc:paper:2609.22961 → doc:official:eu_ai_act
- 边：`term:risk management` --mentioned_in--> `doc:paper:2609.22961`
- 边：`doc:paper:2609.22961` --cites--> `doc:official:eu_ai_act`
- evidence `chunk-f1e362206516aa8101a6eb75` [120:135] quote='risk management' 回读=OK （term:risk management → doc:paper:2609.22961）
    - 上下文：…systems,” 2025, arXiv preprint arXiv:2505.06817. [Online]. risk management framework (AI RMF 1.0),” National Institute of Available: h…
- evidence `chunk-493df5df913a27ffc52bd9e7` [565:592] quote='Artificial Intelligence act' 回读=OK （paper:2609.22961 → official:eu_ai_act）
    - 上下文：…ts to a named subject, delegated task, Huafu Li and Jia Xia are with China Mobile Jiutian Artificial Intelligence action, relying party, trust boundary, and adverse condition. Technology (Beijing) Co., Ltd.…
- 与候选声明链路一致：False

### BMH-019｜adversarial 出现在哪些文档中？

- 节点：term:adversarial → doc:paper:2609.22961 → doc:official:eu_ai_act
- 边：`term:adversarial` --mentioned_in--> `doc:paper:2609.22961`
- 边：`doc:paper:2609.22961` --cites--> `doc:official:eu_ai_act`
- evidence `chunk-77cc1f6556b9882dbecece05` [180:191] quote='adversarial' 回读=OK （term:adversarial → doc:paper:2609.22961）
    - 上下文：…A technical interface, process dent consumers, hard gates, adversarial evidence tests, metrics, boundary, or API call does not alo…
- evidence `chunk-493df5df913a27ffc52bd9e7` [565:592] quote='Artificial Intelligence act' 回读=OK （paper:2609.22961 → official:eu_ai_act）
    - 上下文：…ts to a named subject, delegated task, Huafu Li and Jia Xia are with China Mobile Jiutian Artificial Intelligence action, relying party, trust boundary, and adverse condition. Technology (Beijing) Co., Ltd.…
- 与候选声明链路一致：False

### BMH-020｜benchmark 出现在哪些文档中？

- 节点：term:benchmark → doc:paper:2609.22961 → doc:official:eu_ai_act
- 边：`term:benchmark` --mentioned_in--> `doc:paper:2609.22961`
- 边：`doc:paper:2609.22961` --cites--> `doc:official:eu_ai_act`
- evidence `chunk-3e5a6824a4db54c5d0fa163e` [188:197] quote='benchmark' 回读=OK （term:benchmark → doc:paper:2609.22961）
    - 上下文：…ral object is a trust-evidence envelope for a bounded type, benchmark result, theorem, exhaustive literature review, delegated ac…
- evidence `chunk-493df5df913a27ffc52bd9e7` [565:592] quote='Artificial Intelligence act' 回读=OK （paper:2609.22961 → official:eu_ai_act）
    - 上下文：…ts to a named subject, delegated task, Huafu Li and Jia Xia are with China Mobile Jiutian Artificial Intelligence action, relying party, trust boundary, and adverse condition. Technology (Beijing) Co., Ltd.…
- 与候选声明链路一致：False

### BMH-021｜jailbreak 出现在哪些文档中？

- 节点：term:jailbreak → doc:paper:2609.03999 → doc:source:owasp_genai
- 边：`term:jailbreak` --mentioned_in--> `doc:paper:2609.03999`
- 边：`doc:paper:2609.03999` --cites--> `doc:source:owasp_genai`
- evidence `chunk-64fda3d9789903475a50de40` [802:811] quote='jailbreak' 回读=OK （term:jailbreak → doc:paper:2609.03999）
    - 上下文：…se adaptations, novel threats such as membership inference, jailbreaking, and model inversion further expose sensitive data in wa…
- evidence `chunk-164cfa4a1cb42c48b5bfcf90` [722:738] quote='OWASP LLM Top 10' 回读=OK （paper:2609.03999 → source:owasp_genai）
    - 上下文：…nt a structured taxonomy that maps web attacks to their emerging manifestations under the OWASP LLM Top 10 risks, clarifying how LLM-specific designs create new web attack surfaces. • Second, we a…
- 与候选声明链路一致：False

### BMH-025｜backdoor 出现在哪些文档中？

- 节点：term:backdoor → doc:paper:2609.03999 → doc:source:owasp_genai
- 边：`term:backdoor` --mentioned_in--> `doc:paper:2609.03999`
- 边：`doc:paper:2609.03999` --cites--> `doc:source:owasp_genai`
- evidence `chunk-acaa6958654b8ae1d90912f1` [832:840] quote='backdoor' 回读=OK （term:backdoor → doc:paper:2609.03999）
    - 上下文：…y and intro- TRA_04: Persistent Data Manipulation ing duces backdoors (CWE-345, CWE-347) LLM_05 Improper Output Han- Unsafe or h…
- evidence `chunk-164cfa4a1cb42c48b5bfcf90` [722:738] quote='OWASP LLM Top 10' 回读=OK （paper:2609.03999 → source:owasp_genai）
    - 上下文：…nt a structured taxonomy that maps web attacks to their emerging manifestations under the OWASP LLM Top 10 risks, clarifying how LLM-specific designs create new web attack surfaces. • Second, we a…
- 与候选声明链路一致：False

### BMH-026｜privacy 出现在哪些文档中？

- 节点：term:privacy → doc:paper:2609.22961 → doc:official:eu_ai_act
- 边：`term:privacy` --mentioned_in--> `doc:paper:2609.22961`
- 边：`doc:paper:2609.22961` --cites--> `doc:official:eu_ai_act`
- evidence `chunk-7643464cb9694b009872c6fb` [379:386] quote='privacy' 回读=OK （term:privacy → doc:paper:2609.22961）
    - 上下文：…machine-readable evidence profile is needed to reliability, privacy, accountability, oversight, and organiza- to bind a delegat…
- evidence `chunk-493df5df913a27ffc52bd9e7` [565:592] quote='Artificial Intelligence act' 回读=OK （paper:2609.22961 → official:eu_ai_act）
    - 上下文：…ts to a named subject, delegated task, Huafu Li and Jia Xia are with China Mobile Jiutian Artificial Intelligence action, relying party, trust boundary, and adverse condition. Technology (Beijing) Co., Ltd.…
- 与候选声明链路一致：False

### BMH-027｜fine-tuning 出现在哪些文档中？

- 节点：term:fine-tuning → doc:paper:2609.03999 → doc:source:owasp_genai
- 边：`term:fine-tuning` --mentioned_in--> `doc:paper:2609.03999`
- 边：`doc:paper:2609.03999` --cites--> `doc:source:owasp_genai`
- evidence `chunk-38059997a940da8a90b0b2e0` [963:974] quote='fine-tuning' 回读=OK （term:fine-tuning → doc:paper:2609.03999）
    - 上下文：…omponents, including pre-trained models, training datasets, fine-tuning pipelines, embedding…
- evidence `chunk-164cfa4a1cb42c48b5bfcf90` [722:738] quote='OWASP LLM Top 10' 回读=OK （paper:2609.03999 → source:owasp_genai）
    - 上下文：…nt a structured taxonomy that maps web attacks to their emerging manifestations under the OWASP LLM Top 10 risks, clarifying how LLM-specific designs create new web attack surfaces. • Second, we a…
- 与候选声明链路一致：False

### BMH-030｜alignment 出现在哪些文档中？

- 节点：term:alignment → doc:paper:2609.22961 → doc:official:eu_ai_act
- 边：`term:alignment` --mentioned_in--> `doc:paper:2609.22961`
- 边：`doc:paper:2609.22961` --cites--> `doc:official:eu_ai_act`
- evidence `chunk-3bf1b75edbb069a5704f46c9` [923:932] quote='alignment' 回读=OK （term:alignment → doc:paper:2609.22961）
    - 上下文：…or-reliance. Verifier-policy mismatch supplies the same en- alignment therefore provides design traceability, not a claim…
- evidence `chunk-493df5df913a27ffc52bd9e7` [565:592] quote='Artificial Intelligence act' 回读=OK （paper:2609.22961 → official:eu_ai_act）
    - 上下文：…ts to a named subject, delegated task, Huafu Li and Jia Xia are with China Mobile Jiutian Artificial Intelligence action, relying party, trust boundary, and adverse condition. Technology (Beijing) Co., Ltd.…
- 与候选声明链路一致：False

## 三、未连通（11 条，保留 no_path）

| 题号 | 起始术语 | 目标文档 | 术语是否可达 | 失败原因 |
| --- | --- | --- | --- | --- |
| BMH-011 | AUROC | paper:2609.28915 | True | 图中 term:AUROC 到 doc:paper:2609.28915 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-012 | kernel-level | paper:2609.28915 | False | 图中找不到端点（起始='kernel-level'，目标='doc:paper:2609.28915'） |
| BMH-013 | multi-agent | paper:2609.28915 | True | 图中 term:multi-agent 到 doc:paper:2609.28915 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-015 | prompt injection | source:security_blog | True | 图中 term:prompt injection 到 doc:source:security_blog 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-018 | Qwen3 | paper:2606.15617 | False | 图中找不到端点（起始='Qwen3'，目标='doc:paper:2606.15617'） |
| BMH-022 | model poisoning | official:eu_ai_act | True | 图中 term:model poisoning 到 doc:official:eu_ai_act 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-023 | agent security | paper:2609.28915 | True | 图中 term:agent security 到 doc:paper:2609.28915 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-024 | chain-of-thought | paper:2606.15617 | True | 图中 term:chain-of-thought 到 doc:paper:2606.15617 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-028 | vulnerability | official:eu_ai_act | True | 图中 term:vulnerability 到 doc:official:eu_ai_act 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-029 | detector | paper:2609.28915 | True | 图中 term:detector 到 doc:paper:2609.28915 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |
| BMH-031 | hallucination | paper:2609.28915 | True | 图中 term:hallucination 到 doc:paper:2609.28915 不连通：当前图只有事件→组件、组件/术语→文档 两类边，没有文档到文档的边 |

## 四、复现命令

```
.venv\Scripts\python.exe tools\multihop_path_retriever.py --candidates evaluation\b_multihop_candidates.json --edges evaluation\b_cross_document_edges_20261002_v2.json --out artifacts\b_eval\multihop_path_validation_20261002_v2.json
```
