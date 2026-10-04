"""B 任务：已入库 RAG 语料的检索回归测试。

这些用例验证的是**检索层**（``rag_corpus.search`` 的关键词检索）能否命中文档，
不是问答金标准，也不评价答案正确性。期望值全部来自语料中的真实内容：
每个 ``must_include`` 都先在实际语料上验证过确实存在该术语。

语料位于 B 任务的独立数据目录 ``D:\\ICT\\intel-data-b``。若该目录不存在
（例如在别的机器上跑测试），整个模块会被跳过，而不是产生假失败。
测试只执行 SELECT，不写入语料。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import config, rag_corpus, storage

B_DATA_DIR = Path(r"D:\ICT\intel-data-b")

# (case_id, query, 必须命中的 document_key, 说明)
CASES: list[tuple[str, str, list[str], str]] = [
    ("single-title", "Parameter-Efficient Fine-Tuning", ["paper:2501.13787"],
     "论文标题中的完整词组"),
    ("single-sysname", "DistillGuard", ["paper:2609.28996"],
     "论文自造系统名"),
    ("single-sysname2", "OllamaDrama", ["paper:2609.29757"],
     "论文自造系统名"),
    ("single-term", "preemption", ["paper:2609.29808"],
     "技术术语"),
    ("control-char-adj", "GeLU", ["paper:2501.13787"],
     "控制字符附近的术语仍可命中"),
    ("single-acronym", "Derm7pt", ["paper:2606.15617"],
     "数据集缩写"),
    ("non-paper-source", "European Union AI Act", ["official:eu_ai_act"],
     "非论文来源（官方 PDF）"),
    ("single-word", "grader", ["paper:2609.29333"],
     "常见单词仍应命中文档"),
    ("cross-auroc", "AUROC", ["paper:2609.29429", "paper:2609.28915"],
     "跨文档：两篇论文共用指标缩写"),
    ("cross-kernel", "kernel-level", ["paper:2609.28915", "paper:2609.29808"],
     "跨文档：两篇论文共用技术术语"),
    ("cross-rl", "reinforcement learning", ["paper:2609.29429", "paper:2609.29230"],
     "跨文档：相同方法学主题"),
    ("cross-multiagent", "multi-agent", ["paper:2609.28900", "paper:2609.30028"],
     "跨文档：相同研究对象"),
    ("cross-malicious", "malicious package", ["paper:2609.28996", "source:security_blog"],
     "跨文档：论文与安全博客"),
    ("cross-transparency", "transparency obligations",
     ["official:eu_ai_act", "source:security_blog"],
     "跨文档：法规与博客"),
    ("cross-nistrmf", "NIST AI Risk Management Framework",
     ["source:nist_ai_rmf", "official:eu_ai_act"],
     "跨文档：标准页与法规 PDF"),
    ("late-eu-ai-act", "Schengen", ["official:eu_ai_act"],
     "长文档中后段（849 块，术语仅出现在后 25%）"),
    ("late-paper-a", "paraphrased", ["paper:2609.28915"],
     "长文档中后段（249 块，术语仅出现在后 25%）"),
    ("late-paper-b", "benign", ["paper:2609.29429"],
     "长文档中后段（248 块）"),
    ("mixed-source-type", "risk management",
     ["official:eu_ai_act", "source:nist_ai_rmf"],
     "不同来源类型（官方 PDF + 标准 HTML）"),
]

# 明确要求"跨文档"的用例：必须命中 >= 2 个不同 document_key
CROSS_DOCUMENT_CASES = {
    "cross-auroc", "cross-kernel", "cross-rl", "cross-multiagent",
    "cross-malicious", "cross-transparency", "cross-nistrmf", "mixed-source-type",
}


@pytest.fixture()
def b_corpus(monkeypatch):
    """把配置指向 B 任务的独立语料目录（只读使用）。"""
    if not (B_DATA_DIR / "intel.sqlite").is_file():
        pytest.skip(f"B 任务语料目录不存在：{B_DATA_DIR}")
    monkeypatch.setattr(config, "DATA_DIR", B_DATA_DIR)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", B_DATA_DIR / "snapshots")
    monkeypatch.setattr(config, "DB_PATH", B_DATA_DIR / "intel.sqlite")
    return B_DATA_DIR


def _document_keys() -> dict[str, str]:
    with storage.connect() as conn:
        return {
            row["id"]: row["document_key"]
            for row in conn.execute("SELECT id, document_key FROM rag_documents").fetchall()
        }


@pytest.mark.parametrize(
    "case_id,query,must_include,note", CASES, ids=[case[0] for case in CASES]
)
def test_retrieval_hits_expected_documents(b_corpus, case_id, query, must_include, note):
    """每个查询都必须命中指定文档；命中排名记录在断言信息里。"""
    keys = _document_keys()
    hits = rag_corpus.search(query, limit=500)
    assert hits, f"{case_id}（{note}）：查询 {query!r} 没有任何命中"

    hit_keys = [keys[h["document_id"]] for h in hits]
    missing = [key for key in must_include if key not in hit_keys]
    assert not missing, (
        f"{case_id}（{note}）：查询 {query!r} 未命中 {missing}；"
        f"实际命中文档 {sorted(set(hit_keys))}"
    )

    ranking = {key: hit_keys.index(key) + 1 for key in must_include}
    assert all(rank >= 1 for rank in ranking.values()), ranking


@pytest.mark.parametrize(
    "case_id,query,must_include,note",
    [case for case in CASES if case[0] in CROSS_DOCUMENT_CASES],
    ids=[case[0] for case in CASES if case[0] in CROSS_DOCUMENT_CASES],
)
def test_cross_document_queries_span_multiple_documents(
    b_corpus, case_id, query, must_include, note
):
    """跨文档用例必须同时命中 >= 2 个**不同**的文档。

    注意：这只证明检索器返回了多个文档的命中，**不等于**系统完成了跨文档推理。
    """
    keys = _document_keys()
    hits = rag_corpus.search(query, limit=500)
    hit_keys = {keys[h["document_id"]] for h in hits}
    assert len(hit_keys) >= 2, f"{case_id}：只命中 {hit_keys}"
    assert set(must_include) <= hit_keys, f"{case_id}：缺少 {set(must_include) - hit_keys}"


def test_chunk_with_control_characters_is_still_retrievable(b_corpus):
    """含 NUL/控制字符的分块仍然可以被它自己的词命中。

    取该分块自身的长词作为查询，逐个尝试；只要有一个词能把它检索回来即通过。
    这是对"控制字符是否破坏词法检索"的直接验证。
    """
    with storage.connect() as conn:
        row = conn.execute(
            """SELECT id, text FROM rag_chunks
               WHERE instr(CAST(text AS BLOB), x'00') > 0 LIMIT 1"""
        ).fetchone()
    if row is None:
        pytest.skip("当前语料中没有含 NUL 的分块")

    candidates = [w for w in re.findall(r"[A-Za-z][A-Za-z]{5,}", row["text"])][:6]
    assert candidates, "含 NUL 的分块里没有可用作查询的长词"

    for term in candidates:
        hits = rag_corpus.search(term, limit=500)
        if row["id"] in {hit["chunk_id"] for hit in hits}:
            return
    pytest.fail(f"含 NUL 的分块 {row['id']} 无法被自身任一词命中：{candidates}")


def test_known_low_quality_document_is_flagged_by_its_size(b_corpus):
    """记录已知缺陷：MITRE ATLAS 页面为 JS 渲染，静态正文几乎为空。

    该文档目前只剩极少量字符，检索价值为零。本测试只是把这个已知状态固定下来
    （便于将来修复后被注意到），**不代表这是期望行为**。
    """
    with storage.connect() as conn:
        row = conn.execute(
            """SELECT d.id, d.document_key,
                      (SELECT COUNT(*) FROM rag_chunks c WHERE c.version_id=d.current_version_id) AS chunks,
                      LENGTH(CAST(v.extracted_text AS BLOB)) AS chars
               FROM rag_documents d JOIN rag_document_versions v ON v.id=d.current_version_id
               WHERE d.source_id='mitre_atlas'"""
        ).fetchone()
    if row is None:
        pytest.skip("语料中没有 mitre_atlas 文档")
    assert row["chunks"] == 1
    assert (row["chars"] or 0) <= 32, "MITRE ATLAS 正文长度发生变化，请复查该文档质量"


def test_rss_aggregate_documents_are_single_whole_feed_documents(b_corpus):
    """记录已知事实：security_blog / nist_news 是整份 RSS 聚合，不是单篇文章。"""
    with storage.connect() as conn:
        rows = conn.execute(
            """SELECT d.document_key, COUNT(c.id) AS chunks
               FROM rag_documents d LEFT JOIN rag_chunks c ON c.version_id=d.current_version_id
               WHERE d.source_id IN ('security_blog','nist_news')
               GROUP BY d.id"""
        ).fetchall()
    if not rows:
        pytest.skip("语料中没有 RSS 聚合文档")
    assert {row["document_key"] for row in rows} == {"source:security_blog", "source:nist_news"}
    assert all(row["chunks"] > 100 for row in rows), "RSS 聚合文档的分块数异常"
