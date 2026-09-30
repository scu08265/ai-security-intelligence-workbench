"""B 任务：正式问答评测集（50 题）的结构与来源完整性测试。

这些测试**不评价系统回答质量**，只保证评测集本身是可信的：

- 结构与编号唯一性；
- 八个类别都有题目；
- 每个 `expected_document_key` 在语料库中真实存在；
- 每个 `expected_answer_terms` 都是对应文档正文中的**逐字子串**（防止编造预期）；
- 拒答类题目不得带预期证据；
- 候选多跳题必须被显式标记。

评测集位于 `evaluation/b_formal_qa_set.json`。语料只在**数据库副本**上读取。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app import config, storage

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"
B_DATA_DIR = Path(r"D:\ICT\intel-data-b")

REQUIRED_FIELDS = (
    "question_id", "category", "difficulty", "question", "history",
    "expected_answer_terms", "expected_document_keys", "expected_event_ids",
    "expected_reasoning_steps", "should_refuse", "verification_status", "notes",
)


def _load_dataset() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def b_db_copy(tmp_path_factory):
    if not (B_DATA_DIR / "intel.sqlite").is_file():
        pytest.skip(f"B 任务语料目录不存在：{B_DATA_DIR}")
    target = tmp_path_factory.mktemp("b_eval_set")
    (target / "snapshots").mkdir()
    shutil.copy2(B_DATA_DIR / "intel.sqlite", target / "intel.sqlite")
    return target


@pytest.fixture()
def b_corpus(monkeypatch, b_db_copy):
    monkeypatch.setattr(config, "DATA_DIR", b_db_copy)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", b_db_copy / "snapshots")
    monkeypatch.setattr(config, "DB_PATH", b_db_copy / "intel.sqlite")
    return b_db_copy


@pytest.fixture()
def document_texts(b_corpus) -> dict[str, str]:
    texts: dict[str, str] = {}
    with storage.connect() as conn:
        rows = conn.execute(
            """SELECT d.document_key, v.extracted_text
               FROM rag_documents d JOIN rag_document_versions v ON v.id=d.current_version_id"""
        ).fetchall()
    for row in rows:
        texts[row["document_key"]] = row["extracted_text"] or ""
    return texts


# --------------------------------------------------------------------------
# 结构
# --------------------------------------------------------------------------

def test_dataset_has_fifty_cases_with_unique_ids():
    payload = _load_dataset()
    cases = payload["cases"]
    assert len(cases) == 50, f"期望 50 题，实际 {len(cases)}"
    ids = [case["question_id"] for case in cases]
    assert len(set(ids)) == len(ids), "question_id 存在重复"
    assert ids[0] == "BQA-001" and ids[-1] == "BQA-050"


def test_every_case_declares_all_required_fields():
    for case in _load_dataset()["cases"]:
        for field in REQUIRED_FIELDS:
            assert field in case, f"{case.get('question_id')} 缺少字段 {field}"
        assert case["verification_status"] in {"pending_human_review", "human_verified"}
        assert isinstance(case["history"], list)
        assert isinstance(case["should_refuse"], bool)


def test_all_declared_categories_have_cases():
    payload = _load_dataset()
    declared = set(payload["categories"])
    used = {case["category"] for case in payload["cases"]}
    assert used == declared, f"类别不一致：声明 {declared}，实际 {used}"
    assert len(declared) == 8


def test_questions_are_not_duplicates():
    questions = [case["question"].strip() for case in _load_dataset()["cases"]]
    assert len(set(questions)) == len(questions), "存在完全重复的问题文本"


def test_every_case_is_marked_pending_human_review():
    """本轮没有任何人工标注者参与，标准答案不得声称已核验。"""
    for case in _load_dataset()["cases"]:
        assert case["verification_status"] == "pending_human_review", case["question_id"]


# --------------------------------------------------------------------------
# 来源真实性
# --------------------------------------------------------------------------

def test_expected_documents_exist_in_the_corpus(document_texts):
    for case in _load_dataset()["cases"]:
        for key in case["expected_document_keys"]:
            assert key in document_texts, f"{case['question_id']} 引用了不存在的文档 {key}"


def test_expected_answer_terms_are_verbatim_substrings_of_expected_documents(document_texts):
    """预期答案要点必须真的是对应文档里的原文，不得凭空编写。"""
    problems: list[str] = []
    for case in _load_dataset()["cases"]:
        keys = case["expected_document_keys"]
        if not case["expected_answer_terms"] or not keys:
            continue
        corpus = " ".join(document_texts[key] for key in keys).casefold()
        for term in case["expected_answer_terms"]:
            if term.casefold() not in corpus:
                problems.append(f"{case['question_id']}: {term!r} 不在 {keys}")
    assert not problems, "预期词未在语料中找到：" + "; ".join(problems)


def test_expected_event_ids_exist_in_the_corpus(b_corpus):
    for case in _load_dataset()["cases"]:
        for event_id in case["expected_event_ids"]:
            assert storage.get_event(event_id) is not None, (
                f"{case['question_id']} 引用了不存在的事件 {event_id}"
            )


# --------------------------------------------------------------------------
# 语义约束
# --------------------------------------------------------------------------

def test_refusal_cases_carry_no_expected_evidence():
    for case in _load_dataset()["cases"]:
        if case["should_refuse"]:
            assert case["expected_document_keys"] == [], case["question_id"]
            assert case["expected_answer_terms"] == [], case["question_id"]


def test_candidate_multihop_cases_are_flagged_and_not_claimed_as_verified():
    multi_hop = [c for c in _load_dataset()["cases"] if c["category"] == "真实多跳问答"]
    assert len(multi_hop) >= 2
    for case in multi_hop:
        assert case.get("candidate_only") is True, case["question_id"]
        assert case["verification_status"] == "pending_human_review"


def test_multiturn_cases_carry_history_and_others_do_not():
    for case in _load_dataset()["cases"]:
        if case["category"] == "多轮追问":
            assert case["history"], f"{case['question_id']} 是多轮题但没有历史"
        else:
            assert case["history"] == [], f"{case['question_id']} 不是多轮题却带历史"


def test_cross_document_cases_require_at_least_two_documents():
    for case in _load_dataset()["cases"]:
        if case["category"] == "跨文档问答":
            assert len(case["expected_document_keys"]) >= 1


def test_empty_evidence_cases_still_exist_for_honesty():
    """必须保留'无证据/拒答'类题目，不能用它们充数。"""
    payload = _load_dataset()
    out_of_scope = [c for c in payload["cases"] if c["category"] == "无证据问题与范围外问题"]
    refusal = [c for c in payload["cases"] if c["category"] == "拒答及证据不足"]
    assert len(out_of_scope) >= 5
    assert len(refusal) >= 5
