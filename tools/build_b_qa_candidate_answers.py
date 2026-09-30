"""任务二：为 50 道固定问答批量生成**机器候选标准答案**与**统一裁定表**。

层次必须分清（本工具的输出里每一条都带 `suggestion_level`）：

1. `machine_candidate`：从**引用原文**抽取的候选标准答案／候选拒答建议——本工具产出；
2. `auto_review`：自动评审规则判定（`qa_auto_review.json`）——只作参考；
3. `human_gold`：人工确认的金标准——**本工具不产生、也不填写**。

抽取规则（全部机械、可复现，不做语义生成）：

* 应作答且系统有引用：在引用原文里找**包含预期答案要点**的句子；
  找不到就退回引用原文的前若干字符。候选答案因此永远是"证据原文的摘录"。
* 应拒答：候选行为建议为"应拒答"，理由按 `docs/B_REFUSAL_RULES.md` 的 R2/R3/R4 归因，
  并引用 `refusal_failure_classification.json` 的实测分类；两条口径争议题单独标注 `contested`。
* 跨文档 8 题：候选答案列出**每个来源各自支持的事实**，并明确"是否构成综合"需要人工判定。

产出（均为新文件，不覆盖既有产物）：

* `artifacts/b_eval/qa_candidate_answers.json` —— 机器可读的候选标准答案
* `artifacts/b_eval/qa_adjudication_table.csv` —— 50 题统一裁定表（争议题排在最前）

用法::

    python tools/build_b_qa_candidate_answers.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "artifacts" / "b_eval"
QA_DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"
RESULTS = ARTIFACTS / "formal_qa_results.json"
AUTO_REVIEW = ARTIFACTS / "qa_auto_review.json"
REFUSAL_CLASSIFICATION = ARTIFACTS / "refusal_failure_classification.json"
GOLD_WORKSHEET = ARTIFACTS / "qa_gold_standard_worksheet.csv"

# 拒答分类中"规则明确"的失败集合（除泛词口径争议外）
CLEAR_REFUSAL_FAILURES = {
    "candidate_multihop_answered_topically",
    "numeric_token_false_positive",
    "synthesis_request_answered_with_quotes",
}

HUMAN_COLUMNS = ("人工最终标签", "人工核验人", "人工核验时间", "人工备注")
# 裁定表里人工可直接填写、随后回填到金标准工作表的判定列
JUDGEMENT_COLUMNS = ("人工判定_答案正确性", "人工判定_引用准确性", "人工判定_拒答正确性")

# 口径争议：问题本身的"期望行为"存在分歧，需人工裁定
CONTESTED_QUESTIONS = {"BQA-046", "BQA-050"}
# 判据未定义：跨文档"是否真正综合"缺少判定标准
CROSS_DOCUMENT_QUESTIONS = {f"BQA-{i:03d}" for i in range(31, 39)}

REFUSAL_RULE_BY_CLASS = {
    "candidate_multihop_answered_topically":
        ("R4", "仅有主题相关引用不构成多跳关系证据（缺实体—关系—客体路径）"),
    "numeric_token_false_positive": ("R4", "年份/数字词元造成误命中，不构成回答依据"),
    "synthesis_request_answered_with_quotes": ("R3", "全量总结请求不能用若干摘录冒充"),
    "generic_word_answered_from_event_index":
        ("R4", "单个通用词命中事件标题，是否算充分证据存在口径分歧"),
    "correct_refusal": ("R1/R2", "缺少必要证据时拒答正确"),
}


def _clip(text: str, limit: int = 400) -> str:
    text = (text or "").replace("\r", " ")
    return text if len(text) <= limit else text[:limit] + " …（已截断）"


def _has_human_values(path: Path) -> bool:
    """目标 CSV 是否已有人工填写内容（用于避免覆盖人工核验结果）。"""
    if not path.is_file():
        return False
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = [c for c in (reader.fieldnames or []) if c.startswith("人工")]
            return any((row.get(column) or "").strip()
                       for row in reader for column in columns)
    except (OSError, csv.Error):
        return True


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").replace("\n", " "))
    parts = re.split(r"(?<=[。！？.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _extract_candidate_answer(terms: list[str], citations: list[dict]) -> tuple[str, list[str]]:
    """在引用原文里抽取含预期要点的句子；返回 (候选答案, 命中的要点)。"""
    lowered = [str(t).casefold() for t in terms if str(t).strip()]
    picked: list[str] = []
    hit_terms: list[str] = []
    for citation in citations:
        for sentence in _sentences(citation.get("quote") or ""):
            matched = [t for t in lowered if t in sentence.casefold()]
            if matched and sentence not in picked:
                picked.append(sentence)
                hit_terms.extend(t for t in matched if t not in hit_terms)
            if len(picked) >= 3:
                break
        if len(picked) >= 3:
            break
    if not picked:
        for citation in citations[:2]:
            snippet = _clip(citation.get("quote") or "", 220)
            if snippet:
                picked.append(snippet)
    return _clip(" ".join(picked), 700), hit_terms


def _evidence_items(citations: list[dict]) -> list[dict]:
    return [{
        "chunk_id": c.get("chunk_id"),
        "document_key": c.get("document_key"),
        "char_start": c.get("char_start"),
        "char_end": c.get("char_end"),
        "snippet": _clip(c.get("quote") or "", 240),
    } for c in citations]


def _cross_document_facts(citations: list[dict], terms: list[str]) -> list[dict]:
    """跨文档题：按 document_key 汇总"每个来源各自支持的事实"。"""
    by_doc: dict[str, list[dict]] = {}
    for citation in citations:
        by_doc.setdefault(str(citation.get("document_key")), []).append(citation)
    facts = []
    for document, items in by_doc.items():
        text, hits = _extract_candidate_answer(terms, items)
        facts.append({
            "document_key": document,
            "supports": text or "（该文档引用片段未包含预期要点）",
            "term_hits": hits,
        })
    return facts


def _probe_from_case(case: dict, terms: list[str]) -> dict:
    """语料只读探测结果（若 evidence packet 里已算过则由裁定表另附）。"""
    return {"expected_documents": case.get("expected_document_keys") or [],
            "expected_terms": terms}


def build_case(case: dict, record: dict, review: dict, refusal: dict | None) -> dict:
    qid = case["question_id"]
    citations = record.get("citations_detail") or []
    terms = [str(t) for t in (case.get("expected_answer_terms") or [])]
    should_refuse = bool(case["should_refuse"])
    contested = qid in CONTESTED_QUESTIONS
    cross_document = qid in CROSS_DOCUMENT_QUESTIONS
    entry = {
        "question_id": qid,
        "category": case["category"],
        "question": case["question"],
        "expected_action": "应拒答" if should_refuse else "应回答",
        "suggestion_level": "machine_candidate",
        "human_confirmed": False,
        "system_refused": bool(record.get("refused")),
        "contested": contested or cross_document,
        "contested_reason": (
            "问题期望行为存在口径分歧" if contested else
            "跨文档「是否真正综合多个来源」缺少判定标准" if cross_document else None),
        "auto_review": {
            "judgment": review.get("auto_judgment"),
            "confidence": review.get("auto_confidence"),
            "reason": review.get("auto_reason"),
        },
    }
    if should_refuse:
        class_name = (refusal or {}).get("failure_category") or "correct_refusal"
        rule, why = REFUSAL_RULE_BY_CLASS.get(
            class_name, ("R2", "缺少必要证据时应拒答或说明不确定"))
        entry["candidate_answer"] = "应拒答（候选建议）"
        entry["candidate_answer_type"] = "refusal_recommended"
        entry["refusal_rule"] = rule
        entry["rationale"] = f"{why}（实测分类：{class_name}）"
        if (refusal or {}).get("reason"):
            entry["rationale"] += f"；分类依据：{_clip(refusal['reason'], 200)}"
        entry["evidence"] = _evidence_items(citations)
        entry["machine_suggested_label"] = {
            "拒答正确性": "correct" if record.get("refused") and class_name == "correct_refusal"
            else "incorrect" if not record.get("refused") else "unknown",
            "答案正确性": "not_applicable",
            "引用准确性": "not_applicable" if not citations else "unknown",
        }
    else:
        candidate, hits = _extract_candidate_answer(terms, citations)
        entry["candidate_answer"] = candidate or (
            "（系统未返回任何引用，无法从现有输出抽取候选标准答案；"
            "需人工按语料核对题目要求）")
        entry["candidate_answer_type"] = (
            "extractive_with_terms" if hits else "extractive_fallback" if citations
            else "no_evidence")
        entry["evidence"] = _evidence_items(citations)
        entry["matched_terms"] = hits
        probe = _probe_from_case(case, terms)
        corpus_has_evidence = bool(probe["expected_documents"])
        if record.get("document_hit") and record.get("term_hit"):
            suggestion = "correct"
            why = "预期文档被引用命中，且预期要点逐字出现在答案中（机器核对，仍需人工确认完整性）"
        elif record.get("document_hit") or record.get("term_hit"):
            suggestion = "partial"
            why = "预期文档或预期要点只有一项命中（机器核对）"
        elif citations:
            suggestion = "unknown"
            why = "有引用但未命中预期文档/要点，需人工判断是否等价"
        elif corpus_has_evidence:
            suggestion = "incorrect"
            why = "本地语料存在预期文档，但系统未返回任何引用（疑似检索/上下文问题）"
        else:
            suggestion = "unknown"
            why = "无引用且无可靠金标准可依"
        entry["machine_suggested_label"] = {
            "答案正确性": suggestion,
            "引用准确性": "partially_supported" if _quote_stitched(review) else
                        "unknown" if citations else "not_applicable",
            "拒答正确性": "not_applicable",
        }
        entry["rationale"] = why
        if cross_document:
            entry["cross_document_facts"] = _cross_document_facts(citations, terms)
            entry["synthesis_conclusion"] = (
                "无法证明综合：系统输出为多文档引用拼接，"
                "未见跨来源一致性/比较/推理的显式表述，需人工判定"
                if len(entry["cross_document_facts"]) > 1 else
                "只命中单一文档，不构成跨文档综合")
    entry["alternatives"] = _alternatives(qid, should_refuse, contested)
    entry["minimal_human_judgment"] = _minimal_judgment(qid, should_refuse, cross_document,
                                                        contested, entry)
    return entry


def _quote_stitched(review: dict) -> bool:
    for rule in review.get("auto_rules") or []:
        if rule.get("rule") == "R-QA-QUOTE" and rule.get("result") == "pass":
            return True
    return False


def _alternatives(qid: str, should_refuse: bool, contested: bool) -> list[dict]:
    if contested:
        return [
            {"option": "维持「应拒答」口径，判系统 incorrect",
             "consequence": "拒答召回率按 12 道分母计算，该题记为漏拒答"},
            {"option": "改为「应作答」口径",
             "consequence": "需修改题目期望（评测集变更），并重新定义单通用词的可接受证据标准"},
        ]
    if should_refuse:
        return [
            {"option": "确认拒答正确性",
             "consequence": "计入拒答召回率分母（应拒答）；系统作答即记为失败"},
            {"option": "判为 unknown",
             "consequence": "该题单列、不进拒答分母"},
        ]
    return [
        {"option": "确认答案正确性（correct/partial/incorrect）",
         "consequence": "计入答案准确率分母"},
        {"option": "判为 unknown",
         "consequence": "该题单列，不计入分子分母，需在备注写明缺什么证据"},
    ]


def _minimal_judgment(qid: str, should_refuse: bool, cross_document: bool,
                      contested: bool, entry: dict) -> str:
    if contested:
        return "只回答一个问题：该题的期望行为是「应拒答」还是「应作答」？"
    if cross_document:
        return "该题答案是否真的综合了两个来源（而非并列摘录）？"
    if should_refuse:
        return "系统行为是否与拒答规则一致（correct / incorrect）？"
    if entry["candidate_answer_type"] == "no_evidence":
        return "系统答案是否满足题目要求（无引用，需要看事件路径证据）？"
    return "系统答案是否覆盖候选标准答案的要点，是否完整（correct/partial/incorrect）？"


ADJUDICATION_COLUMNS = [
    "question_id", "category", "priority", "contested", "expected_action",
    "question", "system_refused", "system_answer_excerpt", "cited_document_keys",
    "auto_judgment", "candidate_answer_machine", "evidence_summary",
    "contested_dimension", "suggested_label_machine", "suggestion_rationale",
    "option_a", "consequence_a", "option_b", "consequence_b",
    "minimal_judgment",
] + list(JUDGEMENT_COLUMNS) + list(HUMAN_COLUMNS)


def _parse_probe(text: str) -> dict:
    """从工作表的 `corpus_probe_summary` 里解析只读探测到的文档数与词命中数。"""
    documents: dict[str, int] = {}
    terms: dict[str, int] = {}
    if not text:
        return {"documents": documents, "terms": terms}
    head, _, tail = text.partition("预期词命中块数：")
    for part in head.split("；")[0].replace("预期文档条数：", "").split("；"):
        if "=" in part:
            key, _, value = part.partition("=")
            try:
                documents[key.strip()] = int(value.strip())
            except ValueError:
                continue
    for part in tail.split("；"):
        if "=" in part:
            key, _, value = part.partition("=")
            try:
                terms[key.strip()] = int(value.strip())
            except ValueError:
                continue
    return {"documents": documents, "terms": terms}


def load_probe_index(path: Path = GOLD_WORKSHEET) -> dict[str, dict]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["question_id"]: _parse_probe(row.get("corpus_probe_summary", ""))
                for row in csv.DictReader(handle)}


def _dimension(suggestion: str, confidence: str, rationale: str,
               evidence_ids: list[str], status: str = "suggested") -> dict:
    return {"suggestion": suggestion, "status": status, "confidence": confidence,
            "rationale": rationale, "evidence_ids": evidence_ids}


def build_adjudication(case: dict, record: dict, review: dict,
                       refusal: dict | None, probe: dict) -> dict:
    """生成单题的机器辅助裁定（B 类），含三个维度与能力分析。"""
    qid = case["question_id"]
    citations = record.get("citations_detail") or []
    evidence_ids = [str(c.get("chunk_id")) for c in citations if c.get("chunk_id")]
    documents = {k: v for k, v in (probe.get("documents") or {}).items() if v > 0}
    terms = {k: v for k, v in (probe.get("terms") or {}).items() if v > 0}
    should_refuse = bool(case["should_refuse"])
    doc_hit = bool(record.get("document_hit"))
    term_hit = bool(record.get("term_hit"))
    quote_stitched = _quote_stitched(review)
    class_name = (refusal or {}).get("failure_category")
    contested = qid in CONTESTED_QUESTIONS
    cross_document = qid in CROSS_DOCUMENT_QUESTIONS

    # ---- 答案正确性 -------------------------------------------------------
    if should_refuse:
        answer = _dimension("not_applicable", "high",
                            "该题期望拒答，答案正确性维度不适用", [])
    elif cross_document and (doc_hit or term_hit):
        # 统一口径 4：多来源被引用 ≠ 已整合；未证明跨来源整合时最多判 partial
        answer = _dimension(
            "partial", "low",
            "多来源被引用但未证明跨来源信息整合（输出为并列摘录）；"
            "按统一口径「跨文档综合」答案正确性最多判 partial，需人工确认",
            evidence_ids, status="pending_human_review")
    elif doc_hit and term_hit:
        answer = _dimension(
            "correct", "medium",
            f"预期文档被引用命中（{len(citations)} 条引用）且预期要点逐字出现在答案中；"
            "机器核对，仍需人工确认完整性与是否答非所问", evidence_ids)
    elif doc_hit or term_hit:
        answer = _dimension(
            "partial", "low",
            "预期文档或预期要点只有一项命中，可能遗漏关键条件", evidence_ids)
    elif citations:
        answer = _dimension(
            "unknown", "low",
            "有引用但未命中预期文档/要点；引用内容是否等价于题目要求需人工判断",
            evidence_ids, status="pending_human_review")
    elif documents or terms:
        answer = _dimension(
            "incorrect", "medium",
            f"语料中存在预期证据（文档 {sorted(documents)[:2]}、词命中 "
            f"{list(terms.items())[:2]}），系统却未返回任何引用", [])
    else:
        answer = _dimension(
            "unknown", "low", "无引用且无预期证据可依，无法判定",
            [], status="pending_human_review")

    # ---- 引用是否支持答案 -------------------------------------------------
    if not citations:
        citation = _dimension("not_applicable", "high", "系统未返回任何引用", [])
    elif quote_stitched:
        citation = _dimension(
            "partially_supported", "medium",
            "答案正文由引用原文拼接（自动规则 R-QA-QUOTE 通过），文本层可追溯到 chunk；"
            "引用是否支持答案中的**结论**仍需人工判断", evidence_ids)
    else:
        citation = _dimension(
            "unknown", "low",
            "引用可追溯（chunk 可在库中取回），但答案来自结构化事件路径，"
            "无法用引用核验其结论", evidence_ids, status="pending_human_review")

    # ---- 拒答是否正确 -----------------------------------------------------
    if should_refuse:
        if record.get("refused") and class_name == "correct_refusal":
            refusal_dim = _dimension("correct", "high",
                                     "系统拒答，且按拒答规则确属证据不足", [])
        elif not record.get("refused") and class_name in CLEAR_REFUSAL_FAILURES:
            refusal_dim = _dimension(
                "incorrect", "medium",
                f"应拒答却作答，失败分类 {class_name}（规则明确）", evidence_ids)
        elif not record.get("refused"):
            refusal_dim = _dimension(
                "incorrect", "low",
                f"应拒答却作答，失败分类 {class_name or '未分类'}；"
                "该题期望行为本身存在口径分歧，需人工裁定",
                evidence_ids, status="pending_human_review")
        else:
            refusal_dim = _dimension("unknown", "low", "拒答行为与规则无法自动对齐",
                                     evidence_ids, status="pending_human_review")
    elif record.get("refused"):
        refusal_dim = _dimension("incorrect", "medium", "该题应作答，系统却拒答",
                                 evidence_ids)
    else:
        refusal_dim = _dimension("correct", "medium", "该题应作答，系统未拒答", [])

    # ---- 能力分析 ---------------------------------------------------------
    capability: dict[str, dict] = {}
    if case.get("history"):
        capability["multiturn"] = {
            "applies": True,
            "context_used": bool(citations),
            "corpus_had_evidence": bool(documents or terms),
            "conclusion": (
                "系统返回了引用，多轮上下文是否被使用仍需人工确认" if citations else
                "系统未返回引用，而语料中存在预期证据 → 上下文/证据未被使用"
                if (documents or terms) else "系统未返回引用且语料中未见预期证据"),
        }
    if cross_document:
        sources = sorted({str(c.get("document_key")) for c in citations
                          if c.get("document_key")})
        capability["cross_document"] = {
            "applies": True,
            "sources": sources,
            "synthesis_proven": False,
            "conclusion": "多个来源被引用，但输出为并列摘录，未见跨来源比较/推理 → 不能宣称已综合"
            if len(sources) > 1 else "仅命中单一来源，不构成跨文档综合",
        }
    if case["category"] == "真实多跳问答":
        capability["multihop"] = {
            "applies": True,
            "path_available": False,
            "conclusion": "本地图谱无该问题所需的实体—关系—客体路径"
            "（路径器实测 cross_document 0/21），系统仍给出答案",
        }

    pending = any(d["status"] == "pending_human_review" for d in (answer, citation, refusal_dim))
    missing = _missing(case, record, contested, cross_document, documents, terms)
    if not missing and pending:
        missing = "引用内容是否支持答案中的结论需人工判断（引用可追溯 ≠ 引用支持结论）"
    return {
        "question_id": qid,
        "category": case["category"],
        "question": case["question"],
        "tier": "B_machine_assisted_suggestion",
        "human_confirmed": False,
        "expected_action": "应拒答" if should_refuse else "应回答",
        "system_refused": bool(record.get("refused")),
        "auto_review": {
            "tier": "A_machine_auto_detection",
            "judgment": review.get("auto_judgment"),
            "confidence": review.get("auto_confidence"),
        },
        "answer_correctness": answer,
        "citation_support": citation,
        "refusal_correctness": refusal_dim,
        "capability_analysis": capability,
        "contested": contested or cross_document,
        "contested_reason": (
            "问题期望行为存在口径分歧" if contested else
            "跨文档「是否真正综合」缺少判定标准" if cross_document else None),
        "needs_human_review": pending or contested or cross_document,
        "missing_evidence_or_criteria": missing,
    }


def _missing(case: dict, record: dict, contested: bool, cross_document: bool,
             documents: dict, terms: dict) -> str:
    if contested:
        return "缺少『单通用词查询是否应拒答』的评测口径裁定"
    if cross_document:
        return "缺少『多文档引用是否算综合』的判定标准；系统输出无跨来源推理表述"
    if case["should_refuse"]:
        return "需人工按拒答规则确认该题是否确属证据不足"
    if not record.get("citations_detail"):
        if documents or terms:
            return "系统无引用，但语料疑似存在证据（多轮上下文/检索链路待查）"
        return "系统无引用，且语料中未见预期证据，需要人工确认题目要求"
    return ""


MACHINE_ADJUDICATION_COLUMNS = [
    "question_id", "category", "tier", "contested", "needs_human_review",
    "final_review_group", "group_reason", "confirm_field", "key_evidence",
    "expected_action", "system_refused",
    "answer_suggestion", "answer_status", "answer_confidence", "answer_rationale",
    "citation_suggestion", "citation_status", "citation_confidence", "citation_rationale",
    "refusal_suggestion", "refusal_status", "refusal_confidence", "refusal_rationale",
    "capabilities", "evidence_ids", "missing_evidence_or_criteria",
]


def adjudication_row(item: dict) -> dict:
    group, reason, confirm_field = _final_group(item)
    evidence = item["answer_correctness"]["evidence_ids"] or item["citation_support"]["evidence_ids"]
    return {
        "question_id": item["question_id"],
        "category": item["category"],
        "tier": item["tier"],
        "contested": str(bool(item["contested"])),
        "needs_human_review": str(bool(item["needs_human_review"])),
        "final_review_group": group,
        "group_reason": reason,
        "confirm_field": confirm_field,
        "key_evidence": evidence[0] if evidence else "（无引用）",
        "expected_action": item["expected_action"],
        "system_refused": str(item["system_refused"]),
        "answer_suggestion": item["answer_correctness"]["suggestion"],
        "answer_status": item["answer_correctness"]["status"],
        "answer_confidence": item["answer_correctness"]["confidence"],
        "answer_rationale": item["answer_correctness"]["rationale"],
        "citation_suggestion": item["citation_support"]["suggestion"],
        "citation_status": item["citation_support"]["status"],
        "citation_confidence": item["citation_support"]["confidence"],
        "citation_rationale": item["citation_support"]["rationale"],
        "refusal_suggestion": item["refusal_correctness"]["suggestion"],
        "refusal_status": item["refusal_correctness"]["status"],
        "refusal_confidence": item["refusal_correctness"]["confidence"],
        "refusal_rationale": item["refusal_correctness"]["rationale"],
        "capabilities": "；".join(f"{k}: {v.get('conclusion')}"
                                  for k, v in (item["capability_analysis"] or {}).items()),
        "evidence_ids": "；".join(item["answer_correctness"]["evidence_ids"] or
                                  item["citation_support"]["evidence_ids"]),
        "missing_evidence_or_criteria": item["missing_evidence_or_criteria"],
    }


def _final_group(item: dict) -> tuple[str, str, str]:
    """最终预审分组：A 高置信 / B 需快速确认 / C 实质争议或缺评价规则。"""
    answer = item["answer_correctness"]
    citation = item["citation_support"]
    refusal = item["refusal_correctness"]
    capability = item["capability_analysis"] or {}
    if item["contested"]:
        return ("C", item["contested_reason"] or "存在实质性争议", "评价口径/判据")
    if "multihop" in capability:
        return ("B", "多跳能力越界：本地无关系路径却作答，需确认拒答正确性", "拒答正确性")
    if "multiturn" in capability:
        return ("B", "多轮题：系统未使用语料中已有证据，需确认多轮期望与答案要点", "答案正确性")
    if citation["status"] == "pending_human_review":
        return ("B", "引用可追溯但未逐字拼接答案，需确认引用是否支持结论", "引用支持性")
    if answer["suggestion"] == "partial":
        return ("B", "预期文档或要点只命中一项，需确认答案完整性", "答案正确性")
    if answer["suggestion"] == "correct" and citation["suggestion"] == "partially_supported":
        return ("A", "引用原文直接命中预期文档与要点，评价规则明确", "答案正确性")
    if item["expected_action"] == "应拒答" and refusal["suggestion"] == "correct":
        return ("A", "缺证据时拒答，符合拒答规则 R1/R2", "拒答正确性")
    if item["expected_action"] == "应拒答" and refusal["status"] == "suggested":
        return ("A", "应拒答却作答，规则下归因明确", "拒答正确性")
    return ("B", "需人工快速确认答案与引用", "答案正确性")


def summarise(items: list[dict]) -> dict:
    by_dimension = {}
    for dimension in ("answer_correctness", "citation_support", "refusal_correctness"):
        counter = Counter(item[dimension]["suggestion"] for item in items)
        pending = sum(1 for item in items
                      if item[dimension]["status"] == "pending_human_review")
        by_dimension[dimension] = {"suggestions": dict(counter), "pending_human_review": pending}
    by_category: dict[str, Counter] = {}
    for item in items:
        by_category.setdefault(item["category"], Counter())[
            item["answer_correctness"]["suggestion"]] += 1
    return {
        "tier_A_machine_auto_detection": sum(
            1 for item in items if item["auto_review"]["judgment"]),
        "tier_B_machine_assisted_suggestion": len(items),
        "tier_C_human_confirmed_gold": sum(
            1 for item in items if item["human_confirmed"]),
        "contested": sum(1 for item in items if item["contested"]),
        "needs_human_review": sum(1 for item in items if item["needs_human_review"]),
        "by_dimension": by_dimension,
        "by_category_answer_suggestion": {k: dict(v) for k, v in sorted(by_category.items())},
        "capability_coverage": {
            "multiturn": sum(1 for item in items if "multiturn" in item["capability_analysis"]),
            "cross_document": sum(1 for item in items
                                  if "cross_document" in item["capability_analysis"]),
            "multihop": sum(1 for item in items
                            if "multihop" in item["capability_analysis"]),
        },
        "note": "B 类是**机器辅助裁定建议**，不是人工金标准；"
                "C 类需人工填写后才存在，当前为 0",
    }


def build_row(entry: dict, record: dict, priority: str) -> dict:
    citations = record.get("citations_detail") or []
    suggested = "；".join(f"{k}={v}" for k, v in
                          (entry.get("machine_suggested_label") or {}).items())
    alternatives = entry.get("alternatives") or []
    option_a = alternatives[0] if alternatives else {"option": "", "consequence": ""}
    option_b = alternatives[1] if len(alternatives) > 1 else {"option": "", "consequence": ""}
    row = {
        "question_id": entry["question_id"],
        "category": entry["category"],
        "priority": priority,
        "contested": str(bool(entry["contested"])),
        "expected_action": entry["expected_action"],
        "question": entry["question"],
        "system_refused": str(entry["system_refused"]),
        "system_answer_excerpt": _clip(record.get("answer_full") or "", 300),
        "cited_document_keys": "；".join(sorted({str(c.get("document_key"))
                                                 for c in citations})),
        "auto_judgment": entry["auto_review"]["judgment"],
        "candidate_answer_machine": _clip(entry.get("candidate_answer") or "", 400),
        "evidence_summary": "；".join(
            f"{c['chunk_id']}@{c['document_key']}" for c in
            (entry.get("evidence") or [])[:6]) or "（无引用）",
        "contested_dimension": entry.get("contested_reason") or "",
        "suggested_label_machine": suggested,
        "suggestion_rationale": entry.get("rationale") or "",
        "option_a": option_a.get("option", ""),
        "consequence_a": option_a.get("consequence", ""),
        "option_b": option_b.get("option", ""),
        "consequence_b": option_b.get("consequence", ""),
        "minimal_judgment": entry["minimal_human_judgment"],
    }
    for column in HUMAN_COLUMNS:
        row[column] = ""
    for column in JUDGEMENT_COLUMNS:
        row[column] = ""
    return row


FINAL_CONFIRMATION_COLUMNS = [
    "question_id", "category", "final_review_group", "expected_action",
    "question", "system_answer", "system_refused",
    "standard_answer_or_refusal_requirement", "key_evidence",
    "suggested_answer_correctness", "suggested_citation_support",
    "suggested_refusal_correctness", "rationale", "needs_human_review",
    "confirm_field",
    "人工判定_答案正确性", "人工判定_引用准确性", "人工判定_拒答正确性",
    "human_final_judgment_人工最终判定",
    "人工核验人", "人工核验时间", "人工备注",
]


def confirmation_row(entry: dict, item: dict, case: dict, record: dict) -> dict:
    """50 题统一人工确认工作表的一行（机器建议 + 空的人工列）。"""
    citations = record.get("citations_detail") or []
    key_evidence = "；".join(
        f"{c.get('chunk_id')}@{c.get('document_key')}"
        f"（{c.get('char_start')}–{c.get('char_end')}）" for c in citations[:4]) or "（无引用）"
    return {
        "question_id": item["question_id"],
        "category": item["category"],
        "final_review_group": _final_group(item)[0],
        "expected_action": item["expected_action"],
        "question": case["question"],
        "system_answer": _clip(record.get("answer_full") or "", 600),
        "system_refused": str(bool(record.get("refused"))),
        "standard_answer_or_refusal_requirement": _clip(
            entry.get("candidate_answer") or "", 400),
        "key_evidence": _clip(key_evidence, 400),
        "suggested_answer_correctness": item["answer_correctness"]["suggestion"],
        "suggested_citation_support": item["citation_support"]["suggestion"],
        "suggested_refusal_correctness": item["refusal_correctness"]["suggestion"],
        "rationale": "；".join(filter(None, [
            item["answer_correctness"]["rationale"],
            item["citation_support"]["rationale"] if
            item["citation_support"]["suggestion"] in {"unknown", "unsupported"} else "",
            item["refusal_correctness"]["rationale"] if
            item["refusal_correctness"]["suggestion"] in {"incorrect", "unknown"} else "",
        ])),
        "needs_human_review": str(bool(item["needs_human_review"])),
        "confirm_field": _final_group(item)[2],
        "人工判定_答案正确性": "",
        "人工判定_引用准确性": "",
        "人工判定_拒答正确性": "",
        "human_final_judgment_人工最终判定": "",
        "人工核验人": "",
        "人工核验时间": "",
        "人工备注": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成机器候选标准答案与统一裁定表")
    parser.add_argument("--outdir", type=Path, default=ARTIFACTS)
    args = parser.parse_args()

    dataset = json.loads(QA_DATASET.read_text(encoding="utf-8"))["cases"]
    records = {r["question_id"]: r for r in json.loads(
        RESULTS.read_text(encoding="utf-8"))["records"]}
    reviews = {r["question_id"]: r for r in json.loads(
        AUTO_REVIEW.read_text(encoding="utf-8"))["cases"]}
    refusal_cases = {}
    if REFUSAL_CLASSIFICATION.is_file():
        payload = json.loads(REFUSAL_CLASSIFICATION.read_text(encoding="utf-8"))
        for item in payload.get("cases") or []:
            refusal_cases[item["question_id"]] = item

    entries = []
    for case in dataset:
        qid = case["question_id"]
        refusal = refusal_cases.get(qid)
        if refusal is None:
            refusal = {"failure_class": "correct_refusal"} if case["should_refuse"] else None
        entries.append(build_case(case, records.get(qid, {}), reviews.get(qid, {}), refusal))

    payload = {
        "schema_version": "b-qa-candidate-answers-1.0",
        "suggestion_level": "machine_candidate",
        "warning": "本文件是**机器生成的候选标准答案**（引用原文抽取 / 拒答建议），"
                   "不是人工金标准；不得写入人工标签列，也不得当作准确率依据。",
        "counts": {
            "questions": len(entries),
            "contested": sum(1 for e in entries if e["contested"]),
            "with_citations": sum(1 for e in entries if e["evidence"]),
            "refusal_recommended": sum(1 for e in entries
                                       if e["candidate_answer_type"] == "refusal_recommended"),
        },
        "cases": entries,
    }
    (args.outdir / "qa_candidate_answers.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 机器辅助裁定（B 类）+ 分项统计 ---------------------------------
    probe_index = load_probe_index()
    adjudications = [build_adjudication(
        case, records.get(case["question_id"], {}), reviews.get(case["question_id"], {}),
        refusal_cases.get(case["question_id"]) or
        ({"failure_category": "correct_refusal"} if case["should_refuse"] else None),
        probe_index.get(case["question_id"], {})) for case in dataset]
    summary = summarise(adjudications)
    adjudication_payload = {
        "schema_version": "b-qa-machine-adjudication-1.0",
        "tiers": {
            "A_machine_auto_detection": "qa_auto_review.json 的规则判定",
            "B_machine_assisted_suggestion": "本文件：基于现有引用/探测/规则的裁定建议",
            "C_human_confirmed_gold": "人工确认结果，需人工填写后才存在（当前 0 条）",
        },
        "warning": "本文件全部是 B 类机器辅助建议，不得写入人工标签列，"
                   "也不得当作人工准确率；C 类为空。",
        "summary": summary,
        "cases": adjudications,
    }
    (args.outdir / "qa_machine_adjudication.json").write_text(
        json.dumps(adjudication_payload, ensure_ascii=False, indent=1), encoding="utf-8")

    adj_rows = sorted((adjudication_row(item) for item in adjudications),
                      key=lambda r: (not r["contested"] == "True", r["question_id"]))
    adj_sheet = args.outdir / "qa_machine_adjudication.csv"
    with adj_sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MACHINE_ADJUDICATION_COLUMNS)
        writer.writeheader()
        writer.writerows(adj_rows)

    pending_rows = [row for row in adj_rows
                    if row["contested"] == "True" or row["needs_human_review"] == "True"]
    pending_sheet = args.outdir / "qa_pending_human_cases.csv"
    with pending_sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MACHINE_ADJUDICATION_COLUMNS)
        writer.writeheader()
        writer.writerows(pending_rows)

    # 50 题统一人工确认工作表（机器建议齐全 + 人工列留空）
    confirmation_rows = [
        confirmation_row(entry, item, case, records.get(case["question_id"], {}))
        for entry, item, case in zip(entries, adjudications, dataset)]
    order = {"A": 0, "B": 1, "C": 2}
    confirmation_rows.sort(key=lambda r: (order[r["final_review_group"]],
                                          r["question_id"]))
    confirm_sheet = args.outdir / "qa_final_confirmation_worksheet.csv"
    if _has_human_values(confirm_sheet):
        print("⚠️ 已存在人工填写内容，跳过写入以保护人工核验结果:", confirm_sheet)
    else:
        with confirm_sheet.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FINAL_CONFIRMATION_COLUMNS)
            writer.writeheader()
            writer.writerows(confirmation_rows)
        print("最终人工确认工作表:", len(confirmation_rows), "行 →", confirm_sheet)
    groups = Counter(_final_group(item)[0] for item in adjudications)
    print("  分组:", {f"{k} 组": groups[k] for k in ("A", "B", "C")})

    print("机器辅助裁定:", len(adjudications), "条 →", args.outdir / "qa_machine_adjudication.json")
    print("  A 类(自动):", summary["tier_A_machine_auto_detection"],
          "| B 类(建议):", summary["tier_B_machine_assisted_suggestion"],
          "| C 类(人工):", summary["tier_C_human_confirmed_gold"])
    print("  争议:", summary["contested"], "| 需要人工复核:",
          summary["needs_human_review"], "→", pending_sheet.name)
    for dimension, block in summary["by_dimension"].items():
        print(f"  {dimension}: {block['suggestions']} (pending={block['pending_human_review']})")
    groups = Counter(_final_group(item)[0] for item in adjudications)
    print("  最终预审分组:",
          {f"{k} 组": groups[k] for k in ("A", "B", "C") if groups[k]})

    priorities = {c["question_id"]: (
        "P0-争议" if e["contested"] else
        "P1-拒答" if c["should_refuse"] else
        "P2-多轮" if c.get("history") else "P3-常规")
        for c, e in zip(dataset, entries)}
    rows = [build_row(entry, records.get(entry["question_id"], {}),
                      priorities[entry["question_id"]])
            for entry in entries]
    order = {"P0-争议": 0, "P1-拒答": 1, "P2-多轮": 2, "P3-常规": 3}
    rows.sort(key=lambda r: (order[r["priority"]], r["question_id"]))
    table = args.outdir / "qa_adjudication_table.csv"
    with table.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print("候选标准答案:", len(entries), "条 →", args.outdir / "qa_candidate_answers.json")
    print("其中争议/判据未定义:", payload["counts"]["contested"],
          "| 有引用:", payload["counts"]["with_citations"],
          "| 建议拒答:", payload["counts"]["refusal_recommended"])
    print("统一裁定表:", len(rows), "行 →", table)
    for priority in ("P0-争议", "P1-拒答", "P2-多轮", "P3-常规"):
        ids = [r["question_id"] for r in rows if r["priority"] == priority]
        print(f"  {priority}: {len(ids)} 条 {ids if len(ids) <= 12 else ids[:12] + ['…']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
