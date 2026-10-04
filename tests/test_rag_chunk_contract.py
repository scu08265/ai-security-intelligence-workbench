"""B 任务 D-1 回归测试：`app/rag.py::chunks_from_records` 的区间校验契约。

缺陷：该函数先用 `_text()`（内部 `.strip()`）归一文本，再用归一后的长度去校验
`char_start` / `char_end`。因此任何以换行或空白结尾的分块都会被判为"区间不一致"
而**被静默丢弃**——实测曾丢弃 1906 / 3639（52.4%）个合法分块。

修复后：是否"有内容"仍用 strip 判断（保留既有 `text or quote` 回退），但区间校验
使用**存储原文**，`Chunk.text` 也保留原文，从而让引用区间与正文严格对应。
本文件全部为离线单元测试，不读写任何数据库。
"""

from __future__ import annotations

import pytest

from app.rag import chunks_from_records


def _record(text, *, start: int | None = 0, end: int | None = None, **extra) -> dict:
    """构造一条持久化分块记录；end 缺省表示"区间按文本长度自动成立"。"""
    record: dict = {
        "document_id": "doc-test",
        "chunk_id": "chunk-test",
        "snapshot_hash": "a" * 64,
    }
    if text is not None:
        record["text"] = text
    if start is not None:
        record["char_start"] = start
    if end is not None:
        record["char_end"] = end
    record.update(extra)
    return record


# --------------------------------------------------------------------------
# 合法分块：不同结尾/首尾空白都必须被保留
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "case_id,text",
    [
        ("no-trailing-newline", "kernel level evidence supports the verdict"),
        ("one-trailing-newline", "kernel level evidence supports the verdict\n"),
        ("many-trailing-newlines", "kernel level evidence supports the verdict\n\n\n"),
        ("leading-and-trailing-space", "  kernel level evidence supports the verdict  "),
        ("leading-newline-and-trailing-newline", "\nkernel level evidence supports the verdict\n"),
        ("english", "Defensive copying prevents in place reassignment.\n"),
        ("chinese", "供应链风险需要持续监测。\n"),
        ("mixed", "使用 TrustedGuard 组件时需要检查版本范围。\n"),
    ],
)
def test_records_whose_text_has_whitespace_edges_are_kept(case_id, text):
    """文本首尾空白不得导致合法分块被丢弃（D-1 的核心回归）。"""
    record = _record(text, start=1000, end=1000 + len(text))
    chunks = chunks_from_records([record])
    assert len(chunks) == 1, f"{case_id}: 合法分块被丢弃"
    chunk = chunks[0]
    # 文本必须保留原文，引用区间才能与正文严格对应
    assert chunk.text == text, f"{case_id}: 分块文本被改写"
    assert chunk.char_end - chunk.char_start == len(chunk.text)
    assert chunk.char_start == 1000 and chunk.char_end == 1000 + len(text)
    assert chunk.document_id == "doc-test" and chunk.chunk_id == "chunk-test"


def test_trailing_newline_chunk_previously_dropped_is_now_kept():
    """修复前后对照：这一条正是旧实现会丢弃的形态。"""
    text = "Whereas: the following provisions apply.\n"   # 旧实现 strip 后少 1 字符
    chunks = chunks_from_records([_record(text, start=1295, end=1295 + len(text))])
    assert len(chunks) == 1
    assert chunks[0].char_start == 1295
    assert chunks[0].char_end == 1295 + len(text)


# --------------------------------------------------------------------------
# 回退行为：text 为空时使用 quote
# --------------------------------------------------------------------------

@pytest.mark.parametrize("empty", ["", None])
def test_empty_text_falls_back_to_quote(empty):
    quote = "fallback quote body"
    record = _record(empty, quote=quote, start=7, end=7 + len(quote))
    chunks = chunks_from_records([record])
    assert len(chunks) == 1
    assert chunks[0].text == quote
    assert chunks[0].char_start == 7


def test_quote_key_alone_is_accepted():
    quote = "only the quote key is present"
    chunks = chunks_from_records([{"document_id": "d", "chunk_id": "c",
                                   "snapshot_hash": "b" * 64, "quote": quote}])
    assert len(chunks) == 1
    assert chunks[0].text == quote


# --------------------------------------------------------------------------
# 非法记录仍必须被拒绝
# --------------------------------------------------------------------------

def test_range_longer_than_text_is_rejected():
    """区间比正文长 => 无法审计，必须拒绝。"""
    assert chunks_from_records([_record("short body", start=0, end=99)]) == []


def test_range_shorter_than_text_is_rejected():
    assert chunks_from_records([_record("a much longer body", start=0, end=3)]) == []


def test_range_offset_does_not_match_is_rejected():
    text = "abc def"
    assert chunks_from_records([_record(text, start=5, end=5 + len(text) - 1)]) == []


def test_negative_start_is_rejected():
    assert chunks_from_records([_record("abc", start=-1, end=2)]) == []


def test_non_numeric_range_is_rejected():
    assert chunks_from_records([_record("abc", start="x", end=3)]) == []


@pytest.mark.parametrize("missing", ["document_id", "chunk_id", "snapshot_hash"])
def test_records_missing_identity_fields_are_rejected(missing):
    record = _record("abc", start=0, end=3)
    record[missing] = ""
    assert chunks_from_records([record]) == []


@pytest.mark.parametrize("blank", ["", " ", "\n", "\n\n", "   \t  "])
def test_whitespace_only_text_is_rejected(blank):
    """只有空白的记录没有可检索内容，仍应拒绝。"""
    assert chunks_from_records([_record(blank, start=0, end=len(blank))]) == []


# --------------------------------------------------------------------------
# 批量与缺省区间
# --------------------------------------------------------------------------

def test_missing_char_end_defaults_to_start_plus_length():
    """未提供 char_end 时保持既有行为：按文本长度推导。"""
    record = _record("body\n", start=42)
    chunks = chunks_from_records([record])
    assert len(chunks) == 1
    assert chunks[0].char_start == 42
    assert chunks[0].char_end == 42 + len("body\n")


def test_missing_char_start_defaults_to_zero():
    record = _record("body\n", start=None, end=len("body\n"))
    chunks = chunks_from_records([record])
    assert len(chunks) == 1
    assert chunks[0].char_start == 0


def test_mixed_batch_keeps_only_valid_records_without_duplication():
    records = [
        _record("first\n", start=0, end=6, chunk_id="chunk-1"),
        _record("bad", start=0, end=99, chunk_id="chunk-bad"),        # 非法
        _record("second\n", start=6, end=13, chunk_id="chunk-2"),
        _record("  ", start=13, end=15, chunk_id="chunk-blank"),      # 空白
        _record("third", start=13, end=18, chunk_id="chunk-3"),
    ]
    chunks = chunks_from_records(records)
    assert [c.text for c in chunks] == ["first\n", "second\n", "third"]
    assert [c.chunk_id for c in chunks] == ["chunk-1", "chunk-2", "chunk-3"]
    assert len({c.chunk_id for c in chunks}) == len(chunks)  # 无重复


def test_empty_input_returns_empty_list():
    assert chunks_from_records([]) == []
    assert chunks_from_records(None) == []
