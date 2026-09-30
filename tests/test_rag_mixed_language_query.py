"""B 任务 D-2 回归测试：中英混合查询的检索行为。

缺陷：`app/rag.py::retrieve_chunks` 有一条 `len(unique_query) >= 4 and len(matched) < 2`
守卫。中文问句会被切成大量在英文语料中零命中的二字词元，使 `unique_query` 迅速变大，
而真正匹配的只有一个英文专名，于是整条查询被丢弃：

    "DistillGuard"                -> 检索层 12 条命中
    "DistillGuard 是做什么的？"      -> 0 条命中

修复：单一命中只要**具有区分度**（文档频率 ≤ 语料量/20）就允许保留；像 `ai`
这类遍布语料的词仍然被拒绝。没有硬编码任何论文名或专名。

语料来自 B 任务数据目录，测试在**数据库副本**上运行，不触碰真实数据目录。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app import config, rag_corpus, storage
from app.rag import answer_with_rag, chunks_from_records, terms

B_DATA_DIR = Path(r"D:\ICT\intel-data-b")


@pytest.fixture(scope="module")
def b_db_copy(tmp_path_factory):
    """整个模块共用一份数据库副本，避免读取真实数据目录。"""
    if not (B_DATA_DIR / "intel.sqlite").is_file():
        pytest.skip(f"B 任务语料目录不存在：{B_DATA_DIR}")
    target = tmp_path_factory.mktemp("b_rag_query")
    (target / "snapshots").mkdir()
    shutil.copy2(B_DATA_DIR / "intel.sqlite", target / "intel.sqlite")
    return target


@pytest.fixture()
def b_corpus(monkeypatch, b_db_copy):
    monkeypatch.setattr(config, "DATA_DIR", b_db_copy)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", b_db_copy / "snapshots")
    monkeypatch.setattr(config, "DB_PATH", b_db_copy / "intel.sqlite")
    return b_db_copy


def _hit_document_keys(question: str) -> set[str]:
    records = rag_corpus.list_chunk_records(current_only=True)
    # D-1 修复后应全部通过契约校验；这里断言以免 D-1 回归被静默掩盖
    assert len(chunks_from_records(records)) == len(records)
    result = answer_with_rag(question, [], chunks=records)
    with storage.connect() as conn:
        keys = {
            row["id"]: row["document_key"]
            for row in conn.execute("SELECT id, document_key FROM rag_documents").fetchall()
        }
    return {keys[c["document_id"]] for c in result["citations"]}


# --------------------------------------------------------------------------
# 英文专名：加不加中文问句都应命中同一文档
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "proper_noun,expected_key",
    [
        ("DistillGuard", "paper:2609.28996"),
        ("OllamaDrama", "paper:2609.29757"),
        ("Codetta", "paper:2609.28900"),
        ("Derm7pt", "paper:2606.15617"),
    ],
)
def test_bare_proper_noun_hits_its_document(b_corpus, proper_noun, expected_key):
    assert expected_key in _hit_document_keys(proper_noun)


@pytest.mark.parametrize(
    "question,expected_key",
    [
        ("DistillGuard 是做什么的？", "paper:2609.28996"),
        ("OllamaDrama 蜜罐观察到了什么？", "paper:2609.29757"),
        ("Codetta 是什么？", "paper:2609.28900"),
        ("Derm7pt 数据集是什么？", "paper:2606.15617"),
    ],
)
def test_proper_noun_with_chinese_question_still_hits(b_corpus, question, expected_key):
    """D-2 的核心回归：中文问句不得把英文专名的命中抹掉。"""
    assert expected_key in _hit_document_keys(question)


def test_chinese_wording_does_not_change_the_hit_set_for_a_proper_noun(b_corpus):
    bare = _hit_document_keys("DistillGuard")
    with_question = _hit_document_keys("DistillGuard 是做什么的？")
    assert bare == with_question


# --------------------------------------------------------------------------
# 阈值放宽后不得引入误命中
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question",
    [
        "FoobarGuard 是做什么的？",
        "ZzzNonExistentTool 是什么？",
        "asdf qwerty",
        "欧盟法案对透明度的要求",     # 纯中文且无扩展表映射，维持既有不命中行为
    ],
)
def test_unmatched_queries_do_not_hallucinate_hits(b_corpus, question):
    assert _hit_document_keys(question) == set()


def test_ubiquitous_single_token_is_still_rejected(b_corpus):
    """像 "ai" 这种遍布语料的词单独命中不足以支撑回答。"""
    records = rag_corpus.list_chunk_records(current_only=True)
    corpus_size = len(records)
    document_frequency = sum(
        1 for r in records if "ai" in set(terms(" ".join((r.get("title") or "", r.get("text") or ""))))
    )
    assert document_frequency > corpus_size // 20, "前置条件变化：ai 已不再是高频词"
    assert _hit_document_keys("ai 相关的欧盟要求是什么") == set()


# --------------------------------------------------------------------------
# 既有行为不得退化
# --------------------------------------------------------------------------

def test_pure_english_query_still_hits(b_corpus):
    assert _hit_document_keys("kernel level preemption containment") != set()


def test_pure_chinese_query_with_expansion_still_hits(b_corpus):
    """供应链 -> supply/chain（既有扩展表），行为必须保持。"""
    assert _hit_document_keys("供应链风险") != set()


def test_case_punctuation_and_duplicates_do_not_change_results(b_corpus):
    baseline = _hit_document_keys("DistillGuard")
    assert _hit_document_keys("DISTILLGUARD???") == baseline
    assert _hit_document_keys("DistillGuard DistillGuard DistillGuard") == baseline
    assert _hit_document_keys("  distillguard  ") == baseline


def test_terms_keep_repeats_and_deduplication_happens_in_the_ranker():
    """terms() 本身保留重复词；去重发生在 retrieve_chunks 的 unique_query。"""
    repeated = terms("DistillGuard DistillGuard DistillGuard")
    assert set(repeated) == {"distillguard"}
    assert len(repeated) == 3  # terms() 保留重复，去重发生在检索层的 unique_query


# --------------------------------------------------------------------------
# 阶段 A/B 新发现的缺陷：尾随标点被吞进词元、以及中频技术词被误判为无区分度
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected_token",
    [
        ("JevOut:", "jevout"),
        ("JevOut.", "jevout"),
        ("DistillGuard:", "distillguard"),
        ("codetta,", "codetta"),
        ("SAGE;", "sage"),
    ],
)
def test_trailing_punctuation_is_not_part_of_the_token(text, expected_token):
    """正文标题里的 "JevOut:" 曾被切成 "jevout:"，导致该专名永远检索不到。"""
    assert expected_token in terms(text)
    assert f"{expected_token}:" not in terms(text)
    assert f"{expected_token}." not in terms(text)


@pytest.mark.parametrize(
    "text,expected_token",
    [
        ("cve-2026-41106", "cve-2026-41106"),
        ("vllm 0.28.0 版本", "0.28.0"),
        ("vllm-project/vllm", "vllm-project/vllm"),
        ("multi-agent", "multi-agent"),
    ],
)
def test_inner_punctuation_is_preserved(text, expected_token):
    """词内部的分隔符必须保留，不能被一起剥掉。"""
    assert expected_token in terms(text)


def test_jevout_proper_noun_is_now_retrievable(b_corpus):
    """标题为 "JevOut: ..." 的论文现在可以被裸专名检索到。"""
    assert "paper:2609.30243" in _hit_document_keys("JevOut")


@pytest.mark.parametrize(
    "question,expected_key",
    [
        ("kernel-level 在哪些文档中出现？", "paper:2609.28915"),
        ("multi-agent 主题出现在哪些论文中？", "paper:2609.28900"),
    ],
)
def test_mid_frequency_technical_terms_can_carry_a_query(b_corpus, question, expected_key):
    """"kernel-level"(df≈9%)、"multi-agent"(df≈8%) 是中频技术词，不是通用词。"""
    assert expected_key in _hit_document_keys(question)
