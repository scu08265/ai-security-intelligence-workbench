# 剩余关系证据工作包（paper_link / version_range）

共 87 条 = paper_link 37 + version_range 50。**标签列一律留空，等待人工填写。**

---

## 一、paper_link（37 条）

### BREL-PA-0001 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214527440` / `has_paper` / `https://link.springer.com/content/pdf/10.1186/s43556-026-00600-7.pdf`
- **候选值**：`{"pdf_url": "https://link.springer.com/content/pdf/10.1186/s43556-026-00600-7.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214527440]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214527440", "doi": "https://doi.org/10.1186/s43556-026-00600-7", "title": "mRNA lipid nanoparticle vaccines: current status, challenges and future prospects", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "gold", "oa_url": "https://link.springer.com/content/pdf/10.1186/s43556-026-00600-7.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_page_url": "https://doi.org/10.1186/s43556 …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://link.springer.com/content/pdf/10.1186/s43556-026-00600-7.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0002 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214558721` / `has_paper` / `https://link.springer.com/content/pdf/10.1007/s44265-026-00088-7.pdf`
- **候选值**：`{"pdf_url": "https://link.springer.com/content/pdf/10.1007/s44265-026-00088-7.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214558721]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214558721", "doi": "https://doi.org/10.1007/s44265-026-00088-7", "title": "Digital technology risk exposure and corporate key core technology innovation", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "diamond", "oa_url": "https://link.springer.com/content/pdf/10.1007/s44265-026-00088-7.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_page_url": "https://doi.org/10.1007/s44265- …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://link.springer.com/content/pdf/10.1007/s44265-026-00088-7.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0003 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214600341` / `has_paper` / `https://link.springer.com/content/pdf/10.1186/s42400-026-00649-5.pdf`
- **候选值**：`{"pdf_url": "https://link.springer.com/content/pdf/10.1186/s42400-026-00649-5.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214600341]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214600341", "doi": "https://doi.org/10.1186/s42400-026-00649-5", "title": "Pwnagent: a knowledge-guided multi-agent system for automatic exploit generation", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "diamond", "oa_url": "https://link.springer.com/content/pdf/10.1186/s42400-026-00649-5.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_page_url": "https://doi.org/10.1186/s424 …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://link.springer.com/content/pdf/10.1186/s42400-026-00649-5.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0004 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214526768` / `has_paper` / `https://link.springer.com/content/pdf/10.1007/s44163-026-02344-3.pdf`
- **候选值**：`{"pdf_url": "https://link.springer.com/content/pdf/10.1007/s44163-026-02344-3.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214526768]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214526768", "doi": "https://doi.org/10.1007/s44163-026-02344-3", "title": "Poisoning resilient federated learning for secure internet of medical things a systematic review", "publication_year": 2026, "type": "review", "open_access": {"is_oa": true, "oa_status": "gold", "oa_url": "https://link.springer.com/content/pdf/10.1007/s44163-026-02344-3.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_page_url": "https://doi.org/ …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://link.springer.com/content/pdf/10.1007/s44163-026-02344-3.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0005 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214542908` / `has_paper` / `https://www.nature.com/articles/s41598-026-72755-w_reference.pdf`
- **候选值**：`{"pdf_url": "https://www.nature.com/articles/s41598-026-72755-w_reference.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214542908]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214542908", "doi": "https://doi.org/10.1038/s41598-026-72755-w", "title": "Troll detection using generative adversarial network (GAN) based on social network features", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "gold", "oa_url": "https://www.nature.com/articles/s41598-026-72755-w_reference.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_page_url": "https://doi.org/10.1038/ …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://www.nature.com/articles/s41598-026-72755-w_reference.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0006 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214553113` / `has_paper` / `https://www.cambridge.org/engage/api-gateway/coe/assets/orp/resource/item/6ab904c4810b9dcc828178e4/original/override-theatre-governing-the-human-override-of-ai-agent-decisions-as-a-segregated-accountable-control.pdf`
- **候选值**：`{"pdf_url": "https://www.cambridge.org/engage/api-gateway/coe/assets/orp/resource/item/6ab904c4810b9dcc828178e4/original/override-theatre-governing-the-human-override-of-ai-agent-decisions-as-a-segregated-accountable-control.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214553113]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214553113", "doi": "https://doi.org/10.33774/coe-2026-wp8dr", "title": "Override Theatre: Governing the Human Override of AI-Agent Decisions as a Segregated, Accountable Control", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "gold", "oa_url": "https://www.cambridge.org/engage/api-gateway/coe/assets/orp/resource/item/6ab904c4810b9dcc828178e4/original/override-theatre-governing-the-human-override-of-ai- …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://www.cambridge.org/engage/api-gateway/coe/assets/orp/resource/item/6ab904c4810b9dcc828178e4/original/override-theatre-governing-the-human-override-of-ai-agent-decisions-as-a-segregated-accountable-control.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0007 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214449097` / `has_paper` / `https://www.ijisrt.com/assets/upload/files/IJISRT26SEP879.pdf`
- **候选值**：`{"pdf_url": "https://www.ijisrt.com/assets/upload/files/IJISRT26SEP879.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214449097]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214449097", "doi": "https://doi.org/10.38124/ijisrt/26sep879", "title": "AI-Mediated Ethical Communication: Epistemic Totalization the Fabricatable Zone and the Governmental Chain of Custody as Terminus", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "diamond", "oa_url": "https://www.ijisrt.com/assets/upload/files/IJISRT26SEP879.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_ …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://www.ijisrt.com/assets/upload/files/IJISRT26SEP879.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0008 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214468787` / `has_paper` / `https://doi.org/10.34218/ijaiml_05_02_007`
- **候选值**：`{"pdf_url": "https://doi.org/10.34218/ijaiml_05_02_007", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214468787]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214468787", "doi": "https://doi.org/10.34218/ijaiml_05_02_007", "title": "X-MASIR: AN EXPLAINABLE MULTI-AGENT LARGE LANGUAGE MODEL FRAMEWORK FOR AUTOMATED SECURITY INCIDENT RESPONSE", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "gold", "oa_url": "https://doi.org/10.34218/ijaiml_05_02_007", "any_repository_has_fulltext": null}, "primary_location": {"landing_page_url": "https://doi.org/10.34218/ijaiml_0 …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://doi.org/10.34218/ijaiml_05_02_007？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0009 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W4406794439` / `has_paper` / `https://arxiv.org/pdf/2501.13787`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2501.13787", "arxiv_id": "2501.13787", "linked_document_key": "paper:2501.13787"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W4406794439]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W4406794439", "doi": "https://doi.org/10.1007/s11263-026-03004-w", "title": "Parameter-Efficient Fine-Tuning for Foundation Models", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2501.13787", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://doi.org/10.1007/s11263-026-03004-w", "pdf_url": null}, "has_fulltext": true} ｜ 本地 RAG 文档 paper:2501.13787：标题=Parameter-Efficient Fine-Tuning for Foundation Models，分块=170（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2501.13787`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2501.13787`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 6 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2501.13787？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0010 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7125151750` / `has_paper` / `https://s-rsa.com/index.php/agi/article/download/18747/12429`
- **候选值**：`{"pdf_url": "https://s-rsa.com/index.php/agi/article/download/18747/12429", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7125151750]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7125151750", "doi": "https://doi.org/10.70777/si.v3i3.18747", "title": "AI for Mathematics: Progress, Challenges, and Prospects", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "hybrid", "oa_url": "https://s-rsa.com/index.php/agi/article/download/18747/12429", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://doi.org/10.70777/si.v3i3.18747", "pdf_url": "https://s-rsa. …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://s-rsa.com/index.php/agi/article/download/18747/12429？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0011 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7151534166` / `has_paper` / `https://s-rsa.com/index.php/agi/article/download/18746/12428`
- **候选值**：`{"pdf_url": "https://s-rsa.com/index.php/agi/article/download/18746/12428", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7151534166]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7151534166", "doi": "https://doi.org/10.70777/si.v3i3.18746", "title": "Automated Conjecture Resolution with Formal Verification", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "hybrid", "oa_url": "https://s-rsa.com/index.php/agi/article/download/18746/12428", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://doi.org/10.70777/si.v3i3.18746", "pdf_url": "https://s-rsa …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://s-rsa.com/index.php/agi/article/download/18746/12428？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0012 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7213611819` / `has_paper` / `https://s-rsa.com/index.php/agi/article/download/18734/12426`
- **候选值**：`{"pdf_url": "https://s-rsa.com/index.php/agi/article/download/18734/12426", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7213611819]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7213611819", "doi": "https://doi.org/10.70777/si.v3i3.18734", "title": "ScientistTwo: Pioneering the Human Knowledge Frontier with Autonomous AI", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "hybrid", "oa_url": "https://s-rsa.com/index.php/agi/article/download/18734/12426", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://doi.org/10.70777/si.v3i3.18734", "pdf_url" …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://s-rsa.com/index.php/agi/article/download/18734/12426？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0013 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214295679` / `has_paper` / `https://iiardjournals.org/get/RJPST/VOL. 8 NO. 8 2025/Advances in NLP-Driven Analytics 142-212.pdf`
- **候选值**：`{"pdf_url": "https://iiardjournals.org/get/RJPST/VOL. 8 NO. 8 2025/Advances in NLP-Driven Analytics 142-212.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214295679]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214295679", "doi": "https://doi.org/10.56201/rjpst.vol.8.no8.2025.pg142.212", "title": "Advances In NLP-Driven Analytics for Automated Detection of Regulatory Liabilities in High-Volume Contracts", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "bronze", "oa_url": "https://iiardjournals.org/get/RJPST/VOL. 8 NO. 8 2025/Advances in NLP-Driven Analytics 142-212.pdf", "any_repository_has_fulltext": false}, " …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://iiardjournals.org/get/RJPST/VOL. 8 NO. 8 2025/Advances in NLP-Driven Analytics 142-212.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0014 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214338629` / `has_paper` / `https://theamericanjournals.com/index.php/tajmei/article/download/8413/7697/12737`
- **候选值**：`{"pdf_url": "https://theamericanjournals.com/index.php/tajmei/article/download/8413/7697/12737", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214338629]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214338629", "doi": "https://doi.org/10.37547/tajmei/volume08issue09-04", "title": "Explainable Predictive Business Intelligence for Banking: Integrating Machine Learning, SHAP, and Large Language Models for Customer Response Prediction", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "diamond", "oa_url": "https://theamericanjournals.com/index.php/tajmei/article/download/8413/7697/12737", "any_repository_ …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://theamericanjournals.com/index.php/tajmei/article/download/8413/7697/12737？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0015 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214339430` / `has_paper` / `https://annals-csis.org/Volume_48/drp/pdf/6361.pdf`
- **候选值**：`{"pdf_url": "https://annals-csis.org/Volume_48/drp/pdf/6361.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214339430]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214339430", "doi": "https://doi.org/10.15439/2026f6361", "title": "Engineering Least-Privilege Agentic AI Workflows: Patterns, Anti-Patterns, and Practitioner Guidance", "publication_year": 2026, "type": "conference-paper", "open_access": {"is_oa": true, "oa_status": "diamond", "oa_url": "https://annals-csis.org/Volume_48/drp/pdf/6361.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_page_url": "https://doi.org/10.15439/ …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://annals-csis.org/Volume_48/drp/pdf/6361.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0016 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7164892115` / `has_paper` / `https://arxiv.org/pdf/2606.15617`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2606.15617", "arxiv_id": "2606.15617", "linked_document_key": "paper:2606.15617"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7164892115]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7164892115", "doi": "https://doi.org/10.1007/978-3-032-38098-2_48", "title": "NeRD: Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded Chain-of-Thought in Medical Image Diagnosis", "publication_year": 2026, "type": "conference-paper", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2606.15617", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://doi.org/10.100 …（已截断） ｜ 本地 RAG 文档 paper:2606.15617：标题=NeRD: Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded Chain-of-Thought in Medical Image Diagnosis，分块=37（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2606.15617`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2606.15617`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 13 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2606.15617？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0017 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214152392` / `has_paper` / `https://link.springer.com/content/pdf/10.1007/s10270-026-01425-2.pdf`
- **候选值**：`{"pdf_url": "https://link.springer.com/content/pdf/10.1007/s10270-026-01425-2.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214152392]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214152392", "doi": "https://doi.org/10.1007/s10270-026-01425-2", "title": "LangBiTe: model-driven bias testing of text-to-text large language models", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "hybrid", "oa_url": "https://link.springer.com/content/pdf/10.1007/s10270-026-01425-2.pdf", "any_repository_has_fulltext": false}, "primary_location": {"landing_page_url": "https://doi.org/10.1007/s10270-026-0 …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://link.springer.com/content/pdf/10.1007/s10270-026-01425-2.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0018 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214194099` / `has_paper` / `https://jyx.jyu.fi/bitstreams/db4ece2d-fa81-48a1-b8aa-cc3ea87b9b85/download`
- **候选值**：`{"pdf_url": "https://jyx.jyu.fi/bitstreams/db4ece2d-fa81-48a1-b8aa-cc3ea87b9b85/download", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214194099]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214194099", "doi": "https://doi.org/10.5281/zenodo.22932471", "title": "Architectural Taxonomy of LLM and Knowledge Graph Hybrids for Trustworthy AI", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://jyx.jyu.fi/bitstreams/db4ece2d-fa81-48a1-b8aa-cc3ea87b9b85/download", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "http://urn.fi/URN:NBN:fi:jyu-20 …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://jyx.jyu.fi/bitstreams/db4ece2d-fa81-48a1-b8aa-cc3ea87b9b85/download？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0019 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214198864` / `has_paper` / `https://cdn.openai.com/pdf/d04913be-3f6f-4d2b-b283-ff432ef4aaa5/why-language-models-hallucinate.pdf`
- **候选值**：`{"pdf_url": "https://cdn.openai.com/pdf/d04913be-3f6f-4d2b-b283-ff432ef4aaa5/why-language-models-hallucinate.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214198864]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214198864", "doi": "https://doi.org/10.5281/zenodo.22946209", "title": "When AI Hallucination Becomes Action", "publication_year": 2026, "type": "other", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://cdn.openai.com/pdf/d04913be-3f6f-4d2b-b283-ff432ef4aaa5/why-language-models-hallucinate.pdf", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://medium.com/@aridiosilva/when-ai-hallucina …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://cdn.openai.com/pdf/d04913be-3f6f-4d2b-b283-ff432ef4aaa5/why-language-models-hallucinate.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0020 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214222573` / `has_paper` / `https://jyx.jyu.fi/bitstreams/e176a9a3-450d-463a-b755-da56c748c709/download`
- **候选值**：`{"pdf_url": "https://jyx.jyu.fi/bitstreams/e176a9a3-450d-463a-b755-da56c748c709/download", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214222573]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214222573", "doi": "https://doi.org/10.5281/zenodo.22939503", "title": "Quantum Hybridization: Toward Intelligent Hybrids That Are Smarter and Safer Than Their Constituents", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://jyx.jyu.fi/bitstreams/e176a9a3-450d-463a-b755-da56c748c709/download", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "http:// …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://jyx.jyu.fi/bitstreams/e176a9a3-450d-463a-b755-da56c748c709/download？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0021 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214241047` / `has_paper` / `https://ijirt.org/publishedpaper/IJIRT208799_PAPER.pdf`
- **候选值**：`{"pdf_url": "https://ijirt.org/publishedpaper/IJIRT208799_PAPER.pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214241047]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214241047", "doi": "https://doi.org/10.64643/ijirt.208799-459", "title": "Compliance-Aware, Human-Gated Cloud Remediation: An LLM-Augmented, Specificity-Scored Framework for Multi-Jurisdictional Cloud Security Posture Management", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "hybrid", "oa_url": "https://ijirt.org/publishedpaper/IJIRT208799_PAPER.pdf", "any_repository_has_fulltext": false}, "primary_loc …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://ijirt.org/publishedpaper/IJIRT208799_PAPER.pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0022 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214288902` / `has_paper` / `https://arxiv.org/pdf/2609.28915`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.28915", "arxiv_id": "2609.28915", "linked_document_key": "paper:2609.28915"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214288902]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214288902", "doi": "https://doi.org/10.48550/arxiv.2609.28915", "title": "On the Effectiveness of Kernel-Level Evidence for Agent Security", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.28915", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.28915", "pdf_url": "https://arxiv.org/pdf/2609.28915"},  …（已截断） ｜ 本地 RAG 文档 paper:2609.28915：标题=On the Effectiveness of Kernel-Level Evidence for Agent Security，分块=249（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.28915`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.28915`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 5 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.28915？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0023 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214294325` / `has_paper` / `https://arxiv.org/pdf/2609.29808`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.29808", "arxiv_id": "2609.29808", "linked_document_key": "paper:2609.29808"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214294325]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214294325", "doi": "https://doi.org/10.48550/arxiv.2609.29808", "title": "Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.29808", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.29808", "pdf_url": "https://arxiv.org/pdf/ …（已截断） ｜ 本地 RAG 文档 paper:2609.29808：标题=Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution，分块=79（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.29808`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.29808`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 9 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.29808？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0024 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214307780` / `has_paper` / `https://arxiv.org/pdf/2609.30266`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.30266", "arxiv_id": "2609.30266", "linked_document_key": "paper:2609.30266"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214307780]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214307780", "doi": "https://doi.org/10.48550/arxiv.2609.30266", "title": "LLM Agents Can Easily Tamper With Their Own Traces", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.30266", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.30266", "pdf_url": "https://arxiv.org/pdf/2609.30266"}, "has_fulltext" …（已截断） ｜ 本地 RAG 文档 paper:2609.30266：标题=LLM Agents Can Easily Tamper With Their Own Traces，分块=139（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.30266`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.30266`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 6 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.30266？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0025 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214313011` / `has_paper` / `https://arxiv.org/pdf/2609.30243`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.30243", "arxiv_id": "2609.30243", "linked_document_key": "paper:2609.30243"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214313011]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214313011", "doi": "https://doi.org/10.48550/arxiv.2609.30243", "title": "JevOut: Natural Context Can Flip Decision Models", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.30243", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.30243", "pdf_url": "https://arxiv.org/pdf/2609.30243"}, "has_fulltext":  …（已截断） ｜ 本地 RAG 文档 paper:2609.30243：标题=JevOut: Natural Context Can Flip Decision Models，分块=136（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.30243`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.30243`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 6 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.30243？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0026 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214329963` / `has_paper` / `https://arxiv.org/pdf/2609.29429`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.29429", "arxiv_id": "2609.29429", "linked_document_key": "paper:2609.29429"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214329963]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214329963", "doi": "https://doi.org/10.48550/arxiv.2609.29429", "title": "Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.29429", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.29429", "p …（已截断） ｜ 本地 RAG 文档 paper:2609.29429：标题=Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures，分块=248（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.29429`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.29429`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 7 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.29429？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0027 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214342592` / `has_paper` / `https://arxiv.org/pdf/2609.29230`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.29230", "arxiv_id": "2609.29230", "linked_document_key": "paper:2609.29230"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214342592]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214342592", "doi": "https://doi.org/10.48550/arxiv.2609.29230", "title": "EAGER: Enhancing Generative Event Extraction via Reinforcement Learning with Verifiable Rewards", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.29230", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.29230", "pdf_url": "https …（已截断） ｜ 本地 RAG 文档 paper:2609.29230：标题=EAGER: Enhancing Generative Event Extraction via Reinforcement Learning with Verifiable Rewards，分块=116（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.29230`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.29230`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 10 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.29230？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0028 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214358407` / `has_paper` / `https://arxiv.org/pdf/2609.30192`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.30192", "arxiv_id": "2609.30192", "linked_document_key": "paper:2609.30192"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214358407]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214358407", "doi": "https://doi.org/10.48550/arxiv.2609.30192", "title": "SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.30192", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.30192", "pdf_url": "https://arxiv.org/pdf/2609.30 …（已截断） ｜ 本地 RAG 文档 paper:2609.30192：标题=SAGE: Mitigating Long-Horizon Reasoning Biases via Topological Guidance，分块=123（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.30192`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.30192`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 8 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.30192？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0029 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214375324` / `has_paper` / `https://arxiv.org/pdf/2609.28900`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.28900", "arxiv_id": "2609.28900", "linked_document_key": "paper:2609.28900"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214375324]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214375324", "doi": "https://doi.org/10.48550/arxiv.2609.28900", "title": "Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.28900", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.28900", "pdf_url": "https://arxiv.org/pdf/2609.28 …（已截断） ｜ 本地 RAG 文档 paper:2609.28900：标题=Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion，分块=190（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.28900`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.28900`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 8 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.28900？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0030 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214399041` / `has_paper` / `https://arxiv.org/pdf/2609.30028`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.30028", "arxiv_id": "2609.30028", "linked_document_key": "paper:2609.30028"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214399041]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214399041", "doi": "https://doi.org/10.48550/arxiv.2609.30028", "title": "How does Adversarial Influence Scale in Multi-Agent Systems?", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.30028", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.30028", "pdf_url": "https://arxiv.org/pdf/2609.30028"}, "has …（已截断） ｜ 本地 RAG 文档 paper:2609.30028：标题=How does Adversarial Influence Scale in Multi-Agent Systems?，分块=94（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.30028`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.30028`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 7 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.30028？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0031 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214401639` / `has_paper` / `https://arxiv.org/pdf/2609.29228`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.29228", "arxiv_id": "2609.29228", "linked_document_key": "paper:2609.29228"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214401639]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214401639", "doi": "https://doi.org/10.48550/arxiv.2609.29228", "title": "Towards An LLM-Driven Unified Conversion Framework for BT and FSM in Autonomous Intelligent Systems", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.29228", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.29228", "pdf_url": "h …（已截断） ｜ 本地 RAG 文档 paper:2609.29228：标题=Towards An LLM-Driven Unified Conversion Framework for BT and FSM in Autonomous Intelligent Systems，分块=107（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.29228`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.29228`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 7 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.29228？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0032 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214403218` / `has_paper` / `https://arxiv.org/pdf/2609.29757`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.29757", "arxiv_id": "2609.29757", "linked_document_key": "paper:2609.29757"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214403218]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214403218", "doi": "https://doi.org/10.48550/arxiv.2609.29757", "title": "OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Exposed LLM Infrastructure", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.29757", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.29757", "pdf_url": "http …（已截断） ｜ 本地 RAG 文档 paper:2609.29757：标题=OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Exposed LLM Infrastructure，分块=83（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.29757`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.29757`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 8 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.29757？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0033 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214404543` / `has_paper` / `https://arxiv.org/pdf/2609.30217`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.30217", "arxiv_id": "2609.30217", "linked_document_key": "paper:2609.30217"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214404543]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214404543", "doi": "https://doi.org/10.48550/arxiv.2609.30217", "title": "Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.30217", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.30217", "pdf_url": "https://arxiv.org/pdf/2609.30217"}, …（已截断） ｜ 本地 RAG 文档 paper:2609.30217：标题=Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure，分块=136（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.30217`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.30217`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 8 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.30217？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0034 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214508238` / `has_paper` / `https://arxiv.org/pdf/2609.29333`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.29333", "arxiv_id": "2609.29333", "linked_document_key": "paper:2609.29333"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214508238]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214508238", "doi": null, "title": "Where LLM Graders Succeed and Break: Evidence from Two Computer-Science Exams", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.29333", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.29333", "pdf_url": "https://arxiv.org/pdf/2609.29333"}, "has_fulltext": true} ｜ 本地 RAG 文档 paper:2609.29333：标题=Where LLM Graders Succeed and Break: Evidence from Two Computer-Science Exams，分块=185（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.29333`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.29333`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 4 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.29333？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0035 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214508255` / `has_paper` / `https://arxiv.org/pdf/2609.28996`
- **候选值**：`{"pdf_url": "https://arxiv.org/pdf/2609.28996", "arxiv_id": "2609.28996", "linked_document_key": "paper:2609.28996"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214508255]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214508255", "doi": null, "title": "DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis via Static Graph and LLM Distillation", "publication_year": 2026, "type": "preprint", "open_access": {"is_oa": true, "oa_status": "green", "oa_url": "https://arxiv.org/pdf/2609.28996", "any_repository_has_fulltext": true}, "primary_location": {"landing_page_url": "https://arxiv.org/abs/2609.28996", "pdf_url": "https://arxiv.org/pdf/2609 …（已截断） ｜ 本地 RAG 文档 paper:2609.28996：标题=DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis via Static Graph and LLM Distillation，分块=77（可交叉核验主题）
```

**自动规则明细**：
- `R-PL-ARXIV=pass: 可解析出 arXiv 标识符 2609.28996`
- `R-PL-DOC=pass: 本地存在全文文档 paper:2609.28996`
- `R-PL-TITLE=pass: 事件标题与文档首块词元重合 10 个（阈值 3）`

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://arxiv.org/pdf/2609.28996？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0036 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214062101` / `has_paper` / `https://www.sciencedirect.com/science/article/pii/S2590174526007701/pdf`
- **候选值**：`{"pdf_url": "https://www.sciencedirect.com/science/article/pii/S2590174526007701/pdf", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214062101]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214062101", "doi": "https://doi.org/10.1016/j.ecmx.2026.102287", "title": "Enhanced resilience of demand response under hybrid disruptions in renewable- and storage-rich integrated energy systems: A safety-filtered multi-agent deep reinforcement learning framework", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "gold", "oa_url": "https://www.sciencedirect.com/science/article/pii/S2590174526007701/pdf",  …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://www.sciencedirect.com/science/article/pii/S2590174526007701/pdf？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-PA-0037 · paper_link

- **主体 / 关系 / 客体**：`OPENALEX-W7214100311` / `has_paper` / `https://jasianresearch.com/index.php/AJOAIR/article/download/575/832`
- **候选值**：`{"pdf_url": "https://jasianresearch.com/index.php/AJOAIR/article/download/575/832", "arxiv_id": null, "linked_document_key": null}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`snapshots/openalex/6bd28a60997dc9ce70ba4e04a97892b72276d16c7b28ae6d72baccf043886502.json → results[id=W7214100311]`

**证据片段（原文）**：

```
{"id": "https://openalex.org/W7214100311", "doi": "https://doi.org/10.56557/ajoair/2026/v9i1575", "title": "Management of Multidrug-resistant Organisms in the Era of Artificial Intelligence: Emerging Therapeutic Strategies, Predictive Diagnostics, and Antimicrobial Stewardship Applications", "publication_year": 2026, "type": "article", "open_access": {"is_oa": true, "oa_status": "hybrid", "oa_url": "https://jasianresearch.com/index.php/AJOAIR/article/download/575/832", "any_r …（已截断）
```

**自动规则明细**：
- `R-PL-ARXIV=unavailable: pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文`
- `R-PL-DOC=unavailable: 没有 arXiv 标识符，无法定位本地文档`

**主要缺口**：
- 非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，「论文与事件主题一致」无法本地核验。

**需要人工确认的问题**：
1. OpenAlex 记录中的链接是否就是候选 PDF 链接 https://jasianresearch.com/index.php/AJOAIR/article/download/575/832？
1. 该论文与事件的题目/主题是否为同一工作？
1. 本地是否已有该论文全文可用于交叉核验？

**判定规则**：核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

## 二、version_range（50 条）

### BREL-VE-0001 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-41106` / `affects` / `Microsoft 365 Copilot@unknown`
- **候选值**：`{"package": "Microsoft 365 Copilot", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-41106].doc.affected[]（source_id=msrc:965ac81937）`

**证据片段（原文）**：

```
{"package": "Microsoft 365 Copilot", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:965ac81937"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-41106]：标题=Microsoft 365 Copilot Elevation of Privilege Vulnerability、ProductStatuses=[{"ProductID": ["16765"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0002 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-41109` / `affects` / `Visual Studio Code@unknown`
- **候选值**：`{"package": "Visual Studio Code", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-41109].doc.affected[]（source_id=msrc:be7311139e）`

**证据片段（原文）**：

```
{"package": "Visual Studio Code", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:be7311139e"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-41109]：标题=GitHub Copilot and Visual Studio Code Security Feature Bypass Vulnerability、ProductStatuses=[{"ProductID": ["11622"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0003 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-45499` / `affects` / `Azure Open AI@unknown`
- **候选值**：`{"package": "Azure Open AI", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-45499].doc.affected[]（source_id=msrc:fc713234bc）`

**证据片段（原文）**：

```
{"package": "Azure Open AI", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:fc713234bc"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-45499]：标题=Azure OpenAI Elevation of Privilege Vulnerability、ProductStatuses=[{"ProductID": ["12286"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0004 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-47282` / `affects` / `Visual Studio Code@unknown`
- **候选值**：`{"package": "Visual Studio Code", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-47282].doc.affected[]（source_id=msrc:f0c1bd7783）`

**证据片段（原文）**：

```
{"package": "Visual Studio Code", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:f0c1bd7783"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-47282]：标题=GitHub Copilot and Visual Studio Code Information Disclosure Vulnerability、ProductStatuses=[{"ProductID": ["11622"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0005 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-48561` / `affects` / `Microsoft Edge Copilot for Android@unknown`
- **候选值**：`{"package": "Microsoft Edge Copilot for Android", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-48561].doc.affected[]（source_id=msrc:db40986f3a）`

**证据片段（原文）**：

```
{"package": "Microsoft Edge Copilot for Android", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:db40986f3a"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-48561]：标题=Microsoft Edge Copilot Remote Code Execution Vulnerability、ProductStatuses=[{"ProductID": ["21601", "21602"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0006 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-48561` / `affects` / `Microsoft Edge Copilot for IOS@unknown`
- **候选值**：`{"package": "Microsoft Edge Copilot for IOS", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-48561].doc.affected[]（source_id=msrc:a42308afa7）`

**证据片段（原文）**：

```
{"package": "Microsoft Edge Copilot for IOS", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:a42308afa7"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-48561]：标题=Microsoft Edge Copilot Remote Code Execution Vulnerability、ProductStatuses=[{"ProductID": ["21601", "21602"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0007 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-50510` / `affects` / `GitHub Copilot Plugin for JetBrains IDEs@unknown`
- **候选值**：`{"package": "GitHub Copilot Plugin for JetBrains IDEs", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-50510].doc.affected[]（source_id=msrc:d9bec3708c）`

**证据片段（原文）**：

```
{"package": "GitHub Copilot Plugin for JetBrains IDEs", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:d9bec3708c"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-50510]：标题=GitHub Copilot Remote Code Execution Vulnerability、ProductStatuses=[{"ProductID": ["20677"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0008 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-50517` / `affects` / `Microsoft 365 Copilot@unknown`
- **候选值**：`{"package": "Microsoft 365 Copilot", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-50517].doc.affected[]（source_id=msrc:5ac70d5d54）`

**证据片段（原文）**：

```
{"package": "Microsoft 365 Copilot", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:5ac70d5d54"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-50517]：标题=Microsoft M365 Copilot Remote Code Execution Vulnerability、ProductStatuses=[{"ProductID": ["16765"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0009 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-55145` / `affects` / `Microsoft Copilot@unknown`
- **候选值**：`{"package": "Microsoft Copilot", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-55145].doc.affected[]（source_id=msrc:cc090e2b24）`

**证据片段（原文）**：

```
{"package": "Microsoft Copilot", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:cc090e2b24"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-55145]：标题=Outlook Copilot Tampering Vulnerability、ProductStatuses=[{"ProductID": ["21063"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0010 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-56167` / `affects` / `Azure AI Search@unknown`
- **候选值**：`{"package": "Azure AI Search", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-56167].doc.affected[]（source_id=msrc:bc19886686）`

**证据片段（原文）**：

```
{"package": "Azure AI Search", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:bc19886686"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-56167]：标题=Azure AI Search Elevation of Privilege Vulnerability、ProductStatuses=[{"ProductID": ["12318"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0011 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-58617` / `affects` / `Microsoft 365 Copilot for iOS@unknown`
- **候选值**：`{"package": "Microsoft 365 Copilot for iOS", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-58617].doc.affected[]（source_id=msrc:a4811c223f）`

**证据片段（原文）**：

```
{"package": "Microsoft 365 Copilot for iOS", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "msrc:a4811c223f"} ｜ snapshots/msrc/55c916846fc7fefd572044bdcf12f25730296c6ec22ec33e780af01d105c9ca6.json → Vulnerability[CVE=CVE-2026-58617]：标题=M365 Copilot for iOS Elevation of Privilege Vulnerability、ProductStatuses=[{"ProductID": ["21043"], "Type": 3}]（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 原始快照未出现 'unknown' 的任何版本端点；来源可能以结构化 introduced/fixed 表达区间，需人工核验`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0012 · version_range

- **主体 / 关系 / 客体**：`PYSEC-2026-4000` / `affects` / `vllm@< 0.30.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.30.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[PYSEC-2026-4000].doc.affected[]（source_id=osv:acca1ed12f）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.30.0", "fixed_version": "0.30.0", "source_id": "osv:acca1ed12f"} ｜ snapshots/osv/08e1baad2cecde5d9a5c797c318722171dc9832e7329304d9d746947f074b934.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.30.0"}]}]（推导区间=< 0.30.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.30.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.30.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.30.0'，候选='< 0.30.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 97 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.30.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0013 · version_range

- **主体 / 关系 / 客体**：`PYSEC-2026-3998` / `affects` / `vllm@< 0.29.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.29.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[PYSEC-2026-3998].doc.affected[]（source_id=osv:e0084a3c87）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.29.0", "fixed_version": "0.29.0", "source_id": "osv:e0084a3c87"} ｜ snapshots/osv/b9440e819799ff3b43e23a164d61ffdf6be3e85ba4a69cc1799236d645645462.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.29.0"}]}]（推导区间=< 0.29.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.29.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.29.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.29.0'，候选='< 0.29.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 96 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.29.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0014 · version_range

- **主体 / 关系 / 客体**：`PYSEC-2026-3999` / `affects` / `vllm@< 0.30.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.30.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[PYSEC-2026-3999].doc.affected[]（source_id=osv:0f6a728d1b）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.30.0", "fixed_version": "0.30.0", "source_id": "osv:0f6a728d1b"} ｜ snapshots/osv/c30815fb9f87727ed13e2729ac5f69bdc2bf2e4333466f7c08d79f123407d524.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.30.0"}]}]（推导区间=< 0.30.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.30.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.30.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.30.0'，候选='< 0.30.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 97 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.30.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0015 · version_range

- **主体 / 关系 / 客体**：`PYSEC-2026-3997` / `affects` / `vllm@< 0.28.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.28.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[PYSEC-2026-3997].doc.affected[]（source_id=osv:eb4ff39e9b）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.28.0", "fixed_version": "0.28.0", "source_id": "osv:eb4ff39e9b"} ｜ snapshots/osv/5f29c77279f71baaaa32e4a071dc6a660e7b7af485d346508b4418c3b8806550.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.28.0"}]}]（推导区间=< 0.28.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.28.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.28.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.28.0'，候选='< 0.28.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 95 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.28.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0016 · version_range

- **主体 / 关系 / 客体**：`PYSEC-2026-3996` / `affects` / `vllm@< 0.30.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.30.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[PYSEC-2026-3996].doc.affected[]（source_id=osv:5c0b10d9f5）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.30.0", "fixed_version": "0.30.0", "source_id": "osv:5c0b10d9f5"} ｜ snapshots/osv/b478fb82de5d93e18084254420bbfc703a0b6e84ba2c20bab6907f5cbd8cdebb.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.30.0"}]}]（推导区间=< 0.30.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.30.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.30.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.30.0'，候选='< 0.30.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 97 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.30.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0017 · version_range

- **主体 / 关系 / 客体**：`GHSA-8pw2-6jv3-mj5j` / `affects` / `vllm@< 0.28.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.28.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[GHSA-8pw2-6jv3-mj5j].doc.affected[]（source_id=osv:c8c0660a20）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.28.0", "fixed_version": "0.28.0", "source_id": "osv:c8c0660a20"} ｜ snapshots/osv/5ec93b0e68589ed193d2c5bbeb1f7edc0bf869edce96a714ec8c500d02fc1cb3.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.28.0"}]}]（推导区间=< 0.28.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.28.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.28.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.28.0'，候选='< 0.28.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 95 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.28.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0018 · version_range

- **主体 / 关系 / 客体**：`GHSA-hcwq-8wjf-3gcr` / `affects` / `vllm@< 0.24.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.24.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[GHSA-hcwq-8wjf-3gcr].doc.affected[]（source_id=osv:c8928ad5c4）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.24.0", "fixed_version": "0.24.0", "source_id": "osv:c8928ad5c4"} ｜ snapshots/osv/1f26b5e5797b4057a910378c02a1139671eae131bf4560cf65b9328528ab9646.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.24.0"}]}]（推导区间=< 0.24.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.24.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.24.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.24.0'，候选='< 0.24.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 89 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.24.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0019 · version_range

- **主体 / 关系 / 客体**：`PYSEC-2026-3985` / `affects` / `vllm@< 0.28.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.28.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[PYSEC-2026-3985].doc.affected[]（source_id=osv:f18ed0a7b2）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": "< 0.28.0", "fixed_version": "0.28.0", "source_id": "osv:f18ed0a7b2"} ｜ snapshots/osv/a2f3f13da0780b28558d193546127b1ecda72a69c89a1cec62a970930b66d5b7.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.28.0"}]}]（推导区间=< 0.28.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '< 0.28.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.28.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '< 0.28.0'，候选='< 0.28.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 95 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='< 0.28.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0020 · version_range

- **主体 / 关系 / 客体**：`GHSA-wvm9-9g5j-623f` / `affects` / `open-webui@>= 0.8.0, < 0.11.1`
- **候选值**：`{"package": "open-webui", "ecosystem": "PyPI", "range": ">= 0.8.0, < 0.11.1"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[GHSA-wvm9-9g5j-623f].doc.affected[]（source_id=osv:54efcd8db9）`

**证据片段（原文）**：

```
{"package": "open-webui", "ecosystem": "PyPI", "range": ">= 0.8.0, < 0.11.1", "fixed_version": "0.11.1", "source_id": "osv:54efcd8db9"} ｜ snapshots/osv/579265ef2af27fecd42dde2e00017f2b6aa834e84348ec5d19f2eb2be471355b.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0.8.0"}, {"fixed": "0.11.1"}]}]（推导区间=>= 0.8.0, < 0.11.1）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '>= 0.8.0, < 0.11.1' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.8.0', '0.11.1']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '>= 0.8.0, < 0.11.1'，候选='>= 0.8.0, < 0.11.1'`
- `R-VR-VERSIONS=pass: OSV 列出的 24 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='>= 0.8.0, < 0.11.1' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0021 · version_range

- **主体 / 关系 / 客体**：`GHSA-3g9q-v48f-hh9w` / `affects` / `open-webui@>= 0.9.0, < 0.11.1`
- **候选值**：`{"package": "open-webui", "ecosystem": "PyPI", "range": ">= 0.9.0, < 0.11.1"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[GHSA-3g9q-v48f-hh9w].doc.affected[]（source_id=osv:70515ee5f5）`

**证据片段（原文）**：

```
{"package": "open-webui", "ecosystem": "PyPI", "range": ">= 0.9.0, < 0.11.1", "fixed_version": "0.11.1", "source_id": "osv:70515ee5f5"} ｜ snapshots/osv/943ad60707eae33503855dc72e69353747fb3ebfa105a9579e2bae6f9ae5dac1.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0.9.0"}, {"fixed": "0.11.1"}]}]（推导区间=>= 0.9.0, < 0.11.1）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '>= 0.9.0, < 0.11.1' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.9.0', '0.11.1']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '>= 0.9.0, < 0.11.1'，候选='>= 0.9.0, < 0.11.1'`
- `R-VR-VERSIONS=pass: OSV 列出的 11 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='>= 0.9.0, < 0.11.1' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0022 · version_range

- **主体 / 关系 / 客体**：`GHSA-v39v-59xw-j98g` / `affects` / `open-webui@>= 0.9.0, < 0.11.1`
- **候选值**：`{"package": "open-webui", "ecosystem": "PyPI", "range": ">= 0.9.0, < 0.11.1"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[GHSA-v39v-59xw-j98g].doc.affected[]（source_id=osv:1e61cca71c）`

**证据片段（原文）**：

```
{"package": "open-webui", "ecosystem": "PyPI", "range": ">= 0.9.0, < 0.11.1", "fixed_version": "0.11.1", "source_id": "osv:1e61cca71c"} ｜ snapshots/osv/7f6b0730c264a3430be3c50a000a1e6ccf8a04e69fba1d3f48c8b01eb616aedf.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0.9.0"}, {"fixed": "0.11.1"}]}]（推导区间=>= 0.9.0, < 0.11.1）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '>= 0.9.0, < 0.11.1' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.9.0', '0.11.1']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '>= 0.9.0, < 0.11.1'，候选='>= 0.9.0, < 0.11.1'`
- `R-VR-VERSIONS=pass: OSV 列出的 11 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='>= 0.9.0, < 0.11.1' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0023 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-64849` / `affects` / `MLflow@unknown`
- **候选值**：`{"package": "MLflow", "ecosystem": "MLflow", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-64849].doc.affected[]（source_id=kev:9dd6ba7cd5）`

**证据片段（原文）**：

```
{"package": "MLflow", "ecosystem": "MLflow", "range": "unknown", "fixed_version": null, "source_id": "kev:9dd6ba7cd5"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2026-64849]：vendor=MLflow、product=MLflow、dateAdded=2026-08-19、dueDate=2026-09-02、requiredAction=Apply mitigations in accordance with vendor instructions, ensuring compliance with CISA’s BOD 26-04 Prioritizing Security Updates Based on Risk (see URL in Notes) guidance and CISA’s “Forensics Triage …（已截断）（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0024 · version_range

- **主体 / 关系 / 客体**：`CVE-2025-62593` / `affects` / `Ray@unknown`
- **候选值**：`{"package": "Ray", "ecosystem": "Ray-Project", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2025-62593].doc.affected[]（source_id=kev:a820ca6fd8）`

**证据片段（原文）**：

```
{"package": "Ray", "ecosystem": "Ray-Project", "range": "unknown", "fixed_version": null, "source_id": "kev:a820ca6fd8"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2025-62593]：vendor=Ray-Project、product=Ray、dateAdded=2026-08-17、dueDate=2026-08-20、requiredAction=Apply mitigations in accordance with vendor instructions, ensuring compliance with CISA’s BOD 26-04 Prioritizing Security Updates Based on Risk (see URL in Notes) guidance and CISA’s “Forensics Triage …（已截断）（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0025 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-9198` / `affects` / `Langflow@unknown`
- **候选值**：`{"package": "Langflow", "ecosystem": "IBM", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-9198].doc.affected[]（source_id=kev:60fb54585b）`

**证据片段（原文）**：

```
{"package": "Langflow", "ecosystem": "IBM", "range": "unknown", "fixed_version": null, "source_id": "kev:60fb54585b"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2026-9198]：vendor=IBM、product=Langflow、dateAdded=2026-08-04、dueDate=2026-08-07、requiredAction=Apply mitigations in accordance with vendor instructions, ensuring compliance with CISA’s BOD 26-04 Prioritizing Security Updates Based on Risk (see URL in Notes) guidance and CISA’s “Forensics Triage …（已截断）（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0026 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-0770` / `affects` / `Langflow@unknown`
- **候选值**：`{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-0770].doc.affected[]（source_id=kev:e2836e1985）`

**证据片段（原文）**：

```
{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown", "fixed_version": null, "source_id": "kev:e2836e1985"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2026-0770]：vendor=Langflow、product=Langflow、dateAdded=2026-07-21、dueDate=2026-07-24、requiredAction=Apply mitigations in accordance with vendor instructions, ensuring compliance with CISA’s BOD 26-04 Prioritizing Security Updates Based on Risk (see URL in Notes) guidance and CISA’s “Forensics Triage …（已截断）（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0027 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-55255` / `affects` / `Langflow@unknown`
- **候选值**：`{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-55255].doc.affected[]（source_id=kev:17bfdcf2bb）`

**证据片段（原文）**：

```
{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown", "fixed_version": null, "source_id": "kev:17bfdcf2bb"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2026-55255]：vendor=Langflow、product=Langflow、dateAdded=2026-07-07、dueDate=2026-07-10、requiredAction=Apply mitigations in accordance with vendor instructions, ensuring compliance with CISA’s BOD 26-04 Prioritizing Security Updates Based on Risk (see URL in Notes) guidance and CISA’s “Forensics Triage …（已截断）（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0028 · version_range

- **主体 / 关系 / 客体**：`CVE-2025-34291` / `affects` / `Langflow@unknown`
- **候选值**：`{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2025-34291].doc.affected[]（source_id=kev:0238e5afaa）`

**证据片段（原文）**：

```
{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown", "fixed_version": null, "source_id": "kev:0238e5afaa"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2025-34291]：vendor=Langflow、product=Langflow、dateAdded=2026-05-21、dueDate=2026-06-04、requiredAction=Apply mitigations per vendor instructions, follow applicable BOD 22-01 guidance for cloud services, or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0029 · version_range

- **主体 / 关系 / 客体**：`CVE-2026-33017` / `affects` / `Langflow@unknown`
- **候选值**：`{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2026-33017].doc.affected[]（source_id=kev:cc774f968c）`

**证据片段（原文）**：

```
{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown", "fixed_version": null, "source_id": "kev:cc774f968c"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2026-33017]：vendor=Langflow、product=Langflow、dateAdded=2026-03-25、dueDate=2026-04-08、requiredAction=Apply mitigations per vendor instructions, follow applicable BOD 22-01 guidance for cloud services, or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0030 · version_range

- **主体 / 关系 / 客体**：`CVE-2025-68613` / `affects` / `n8n@unknown`
- **候选值**：`{"package": "n8n", "ecosystem": "n8n", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2025-68613].doc.affected[]（source_id=kev:bcf2511640）`

**证据片段（原文）**：

```
{"package": "n8n", "ecosystem": "n8n", "range": "unknown", "fixed_version": null, "source_id": "kev:bcf2511640"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2025-68613]：vendor=n8n、product=n8n、dateAdded=2026-03-11、dueDate=2026-03-25、requiredAction=Apply mitigations per vendor instructions, follow applicable BOD 22-01 guidance for cloud services, or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0031 · version_range

- **主体 / 关系 / 客体**：`GHSA-mcmc-2m55-j8jj` / `affects` / `vllm@>= 0.10.2, < 0.13.0`
- **候选值**：`{"package": "vllm", "ecosystem": "PyPI", "range": ">= 0.10.2, < 0.13.0"}`
- **自动核验**：`supported`（high）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[GHSA-mcmc-2m55-j8jj].doc.affected[]（source_id=osv:31793381df）`

**证据片段（原文）**：

```
{"package": "vllm", "ecosystem": "PyPI", "range": ">= 0.10.2, < 0.13.0", "fixed_version": "0.13.0", "source_id": "osv:31793381df"} ｜ snapshots/osv/05825c4e086d5563d928d48dfc7ed4ddfe492567ca5a781d878e4ccc8817371c.json → affected[].ranges[].events：[{"type": "ECOSYSTEM", "events": [{"introduced": "0.10.2"}, {"fixed": "0.13.0"}]}]（推导区间=>= 0.10.2, < 0.13.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '>= 0.10.2, < 0.13.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['0.10.2', '0.13.0']`
- `R-VR-STRUCTURED=pass: OSV 结构化事件还原出 '>= 0.10.2, < 0.13.0'，候选='>= 0.10.2, < 0.13.0'`
- `R-VR-VERSIONS=pass: OSV 列出的 5 个受影响版本中，0 个不在候选区间内`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='>= 0.10.2, < 0.13.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0032 · version_range

- **主体 / 关系 / 客体**：`CVE-2025-9959` / `affects` / `smolagents@>= 0, < 1.21.0`
- **候选值**：`{"package": "smolagents", "ecosystem": "smolagents", "range": ">= 0, < 1.21.0"}`
- **自动核验**：`supported`（medium）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2025-9959].doc.affected[]（source_id=mitre:7e4dafe046）`

**证据片段（原文）**：

```
{"package": "smolagents", "ecosystem": "smolagents", "range": ">= 0, < 1.21.0", "fixed_version": null, "source_id": "mitre:7e4dafe046", "source_ids": ["mitre:7e4dafe046"]} ｜ snapshots/mitre_cve/01ee9fb7ff63a9d52e0b92173e5a4f59fcebc3314ece65c114ea8eb7192c85e5.json → containers.cna.affected[].versions：[{"lessThan": "1.21.0", "status": "affected", "version": "0", "versionType": "python"}]（推导区间=>= 0, < 1.21.0）
```

**自动规则明细**：
- `R-VR-PARSE=pass: '>= 0, < 1.21.0' 可解析为版本区间`
- `R-VR-SNAPSHOT=pass: 原始快照包含区间端点 ['1.21.0']`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='>= 0, < 1.21.0' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0033 · version_range

- **主体 / 关系 / 客体**：`CVE-2025-6558` / `affects` / `Chromium@unknown`
- **候选值**：`{"package": "Chromium", "ecosystem": "Google", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2025-6558].doc.affected[]（source_id=kev:e46fde0723）`

**证据片段（原文）**：

```
{"package": "Chromium", "ecosystem": "Google", "range": "unknown", "fixed_version": null, "source_id": "kev:e46fde0723"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2025-6558]：vendor=Google、product=Chromium、dateAdded=2025-07-22、dueDate=2025-08-12、requiredAction=Apply mitigations per vendor instructions, follow applicable BOD 22-01 guidance for cloud services, or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0034 · version_range

- **主体 / 关系 / 客体**：`CVE-2025-3248` / `affects` / `Langflow@unknown`
- **候选值**：`{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2025-3248].doc.affected[]（source_id=kev:1eacce3542）`

**证据片段（原文）**：

```
{"package": "Langflow", "ecosystem": "Langflow", "range": "unknown", "fixed_version": null, "source_id": "kev:1eacce3542"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2025-3248]：vendor=Langflow、product=Langflow、dateAdded=2025-05-05、dueDate=2025-05-26、requiredAction=Apply mitigations per vendor instructions, follow applicable BOD 22-01 guidance for cloud services, or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0035 · version_range

- **主体 / 关系 / 客体**：`CVE-2024-4610` / `affects` / `Mali GPU Kernel Driver@unknown`
- **候选值**：`{"package": "Mali GPU Kernel Driver", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2024-4610].doc.affected[]（source_id=kev:c293276891）`

**证据片段（原文）**：

```
{"package": "Mali GPU Kernel Driver", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:c293276891"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2024-4610]：vendor=Arm、product=Mali GPU Kernel Driver、dateAdded=2024-06-12、dueDate=2024-07-03、requiredAction=Apply mitigations per vendor instructions or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0036 · version_range

- **主体 / 关系 / 客体**：`CVE-2024-29988` / `affects` / `SmartScreen Prompt@unknown`
- **候选值**：`{"package": "SmartScreen Prompt", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2024-29988].doc.affected[]（source_id=kev:88cb839535）`

**证据片段（原文）**：

```
{"package": "SmartScreen Prompt", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "kev:88cb839535"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2024-29988]：vendor=Microsoft、product=SmartScreen Prompt、dateAdded=2024-04-30、dueDate=2024-05-21、requiredAction=Apply mitigations per vendor instructions or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0037 · version_range

- **主体 / 关系 / 客体**：`CVE-2023-4211` / `affects` / `Mali GPU Kernel Driver@unknown`
- **候选值**：`{"package": "Mali GPU Kernel Driver", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2023-4211].doc.affected[]（source_id=kev:dc65c96f55）`

**证据片段（原文）**：

```
{"package": "Mali GPU Kernel Driver", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:dc65c96f55"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2023-4211]：vendor=Arm、product=Mali GPU Kernel Driver、dateAdded=2023-10-03、dueDate=2023-10-24、requiredAction=Apply mitigations per vendor instructions or discontinue use of the product if mitigations are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0038 · version_range

- **主体 / 关系 / 客体**：`CVE-2021-29256` / `affects` / `Mali Graphics Processing Unit (GPU)@unknown`
- **候选值**：`{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2021-29256].doc.affected[]（source_id=kev:f041cb213d）`

**证据片段（原文）**：

```
{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:f041cb213d"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2021-29256]：vendor=Arm、product=Mali Graphics Processing Unit (GPU)、dateAdded=2023-07-07、dueDate=2023-07-28、requiredAction=Apply updates per vendor instructions or discontinue use of the product if updates are unavailable.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0039 · version_range

- **主体 / 关系 / 客体**：`CVE-2021-27876` / `affects` / `Backup Exec Agent@unknown`
- **候选值**：`{"package": "Backup Exec Agent", "ecosystem": "Veritas", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2021-27876].doc.affected[]（source_id=kev:cd73f65cd7）`

**证据片段（原文）**：

```
{"package": "Backup Exec Agent", "ecosystem": "Veritas", "range": "unknown", "fixed_version": null, "source_id": "kev:cd73f65cd7"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2021-27876]：vendor=Veritas、product=Backup Exec Agent、dateAdded=2023-04-07、dueDate=2023-04-28、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0040 · version_range

- **主体 / 关系 / 客体**：`CVE-2021-27877` / `affects` / `Backup Exec Agent@unknown`
- **候选值**：`{"package": "Backup Exec Agent", "ecosystem": "Veritas", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2021-27877].doc.affected[]（source_id=kev:71ac15a41b）`

**证据片段（原文）**：

```
{"package": "Backup Exec Agent", "ecosystem": "Veritas", "range": "unknown", "fixed_version": null, "source_id": "kev:71ac15a41b"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2021-27877]：vendor=Veritas、product=Backup Exec Agent、dateAdded=2023-04-07、dueDate=2023-04-28、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0041 · version_range

- **主体 / 关系 / 客体**：`CVE-2021-27878` / `affects` / `Backup Exec Agent@unknown`
- **候选值**：`{"package": "Backup Exec Agent", "ecosystem": "Veritas", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2021-27878].doc.affected[]（source_id=kev:e2e8e74de1）`

**证据片段（原文）**：

```
{"package": "Backup Exec Agent", "ecosystem": "Veritas", "range": "unknown", "fixed_version": null, "source_id": "kev:e2e8e74de1"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2021-27878]：vendor=Veritas、product=Backup Exec Agent、dateAdded=2023-04-07、dueDate=2023-04-28、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0042 · version_range

- **主体 / 关系 / 客体**：`CVE-2023-26083` / `affects` / `Mali Graphics Processing Unit (GPU)@unknown`
- **候选值**：`{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2023-26083].doc.affected[]（source_id=kev:61e498deab）`

**证据片段（原文）**：

```
{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:61e498deab"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2023-26083]：vendor=Arm、product=Mali Graphics Processing Unit (GPU)、dateAdded=2023-04-07、dueDate=2023-04-28、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0043 · version_range

- **主体 / 关系 / 客体**：`CVE-2022-22706` / `affects` / `Mali Graphics Processing Unit (GPU)@unknown`
- **候选值**：`{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2022-22706].doc.affected[]（source_id=kev:b644099a5f）`

**证据片段（原文）**：

```
{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:b644099a5f"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2022-22706]：vendor=Arm、product=Mali Graphics Processing Unit (GPU)、dateAdded=2023-03-30、dueDate=2023-04-20、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0044 · version_range

- **主体 / 关系 / 客体**：`CVE-2022-38181` / `affects` / `Mali Graphics Processing Unit (GPU)@unknown`
- **候选值**：`{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2022-38181].doc.affected[]（source_id=kev:c4b140217d）`

**证据片段（原文）**：

```
{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:c4b140217d"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2022-38181]：vendor=Arm、product=Mali Graphics Processing Unit (GPU)、dateAdded=2023-03-30、dueDate=2023-04-20、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0045 · version_range

- **主体 / 关系 / 客体**：`CVE-2022-4135` / `affects` / `Chromium GPU@unknown`
- **候选值**：`{"package": "Chromium GPU", "ecosystem": "Google", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2022-4135].doc.affected[]（source_id=kev:ae99c22581）`

**证据片段（原文）**：

```
{"package": "Chromium GPU", "ecosystem": "Google", "range": "unknown", "fixed_version": null, "source_id": "kev:ae99c22581"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2022-4135]：vendor=Google、product=Chromium GPU、dateAdded=2022-11-28、dueDate=2022-12-19、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0046 · version_range

- **主体 / 关系 / 客体**：`CVE-2014-6332` / `affects` / `Windows@unknown`
- **候选值**：`{"package": "Windows", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2014-6332].doc.affected[]（source_id=kev:6e45befc4a）`

**证据片段（原文）**：

```
{"package": "Windows", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "kev:6e45befc4a"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2014-6332]：vendor=Microsoft、product=Windows、dateAdded=2022-03-25、dueDate=2022-04-15、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0047 · version_range

- **主体 / 关系 / 客体**：`CVE-2014-4114` / `affects` / `Windows@unknown`
- **候选值**：`{"package": "Windows", "ecosystem": "Microsoft", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2014-4114].doc.affected[]（source_id=kev:eaf4f137b1）`

**证据片段（原文）**：

```
{"package": "Windows", "ecosystem": "Microsoft", "range": "unknown", "fixed_version": null, "source_id": "kev:eaf4f137b1"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2014-4114]：vendor=Microsoft、product=Windows、dateAdded=2022-03-03、dueDate=2022-03-24、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0048 · version_range

- **主体 / 关系 / 客体**：`CVE-2020-10987` / `affects` / `AC1900 Router AC15 Model@unknown`
- **候选值**：`{"package": "AC1900 Router AC15 Model", "ecosystem": "Tenda", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2020-10987].doc.affected[]（source_id=kev:6058689232）`

**证据片段（原文）**：

```
{"package": "AC1900 Router AC15 Model", "ecosystem": "Tenda", "range": "unknown", "fixed_version": null, "source_id": "kev:6058689232"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2020-10987]：vendor=Tenda、product=AC1900 Router AC15 Model、dateAdded=2021-11-03、dueDate=2022-05-03、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0049 · version_range

- **主体 / 关系 / 客体**：`CVE-2021-28663` / `affects` / `Mali Graphics Processing Unit (GPU)@unknown`
- **候选值**：`{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2021-28663].doc.affected[]（source_id=kev:e970a840a0）`

**证据片段（原文）**：

```
{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:e970a840a0"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2021-28663]：vendor=Arm、product=Mali Graphics Processing Unit (GPU)、dateAdded=2021-11-03、dueDate=2021-11-17、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---

### BREL-VE-0050 · version_range

- **主体 / 关系 / 客体**：`CVE-2021-28664` / `affects` / `Mali Graphics Processing Unit (GPU)@unknown`
- **候选值**：`{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown"}`
- **自动核验**：`insufficient_evidence`（low）
- **证据状态**：**direct**
- **证据定位**：`intel.sqlite → events[CVE-2021-28664].doc.affected[]（source_id=kev:64634e014d）`

**证据片段（原文）**：

```
{"package": "Mali Graphics Processing Unit (GPU)", "ecosystem": "Arm", "range": "unknown", "fixed_version": null, "source_id": "kev:64634e014d"} ｜ snapshots/cisa_kev/62c798bffe1334f5ad43853a7ee9d6eb6969e5b98b6755a6e1c901a1b1ae8f5c.json → vulnerabilities[cveID=CVE-2021-28664]：vendor=Arm、product=Mali Graphics Processing Unit (GPU)、dateAdded=2021-11-03、dueDate=2021-11-17、requiredAction=Apply updates per vendor instructions.（无版本区间字段）
```

**自动规则明细**：
- `R-VR-PARSE=unavailable: 'unknown' 不是 PEP 440 区间（可能是厂商自有版本号），无法判定`
- `R-VR-SNAPSHOT=unavailable: 来源 kev 没有可读的文本快照`
- `R-VR-STRUCTURED=unavailable: 本地没有该事件的 OSV 结构化快照（可能来自其他来源）`

**主要缺口**：
- CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。

**需要人工确认的问题**：
1. 事件保存的三元组（package/ecosystem/range）是否与来源一致？
1. 候选 range='unknown' 是具体区间还是「来源未提供」？
1. 若区间来自结构化字段，能否用上游原始字段复核？

**判定规则**：对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。

**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______

---
