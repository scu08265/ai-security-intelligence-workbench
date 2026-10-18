"""A1：把 paper_link 的 21 条 unknown 逐条核到可解释的状态。

规则（按任务书，不猜）：

1. 从 ``pdf_url`` 里提取 DOI（末尾的 ``.pdf`` 先剥掉），与 OpenAlex 记录的 DOI
   **逐字比对**（大小写不敏感，除此外不做任何近似）；
2. 没有 DOI 时，用 URL 里能读出的标题 + 年份做**双匹配**——两项都命中才算；
3. 剩下的写 ``unknown``，并注明缺的是哪一项（OpenAlex DOI / URL DOI / URL 年份 /
   URL 里的标题）。不把"链接存在"写成"主题已核验"。

输入：``evaluation/b_relation_candidates_20261010.json`` 里 ``dimension=paper_link``
且 ``candidate_value`` 有空字段的那 21 条。
输出：``artifacts/b_eval/paper_link_verification_20261018.json``。

用法：
    ./.venv/Scripts/python.exe tools/verify_paper_links.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "evaluation" / "b_relation_candidates_20261010.json"
DEFAULT_DB = ROOT / "work" / "b-corpus" / "intel.sqlite"
OUTPUT = ROOT / "artifacts" / "b_eval" / "paper_link_verification_20261018.json"
OUTPUT_CSV = ROOT / "artifacts" / "b_eval" / "paper_link_verification_20261018.csv"
OUTPUT_DOC = ROOT / "docs" / "B_PAPER_LINK_VERIFICATION_20261018.md"

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>?#]+", re.I)
YEAR_RE = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")
STOPWORDS = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "by"}


def normalize_doi(text: str | None) -> str | None:
    match = DOI_RE.search(text or "")
    if not match:
        return None
    doi = match.group(0).rstrip(".")
    for suffix in (".pdf", ".PDF", ".Pdf"):
        if doi.endswith(suffix):
            doi = doi[: -len(suffix)]
    return doi


def tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text or "").casefold()
    cleaned = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", folded)
    return [word for word in cleaned.split() if word]


def title_tokens(text: str) -> set[str]:
    # 纯数字（页码、卷期、年份）不参与标题匹配；年份另有 YEAR_RE 单独比。
    return {word for word in tokens(text)
            if word not in STOPWORDS and len(word) > 1 and not word.isdigit()}


def url_text(url: str) -> str:
    """URL 路径里能读出的文字（去掉扩展名、把连字符换成空格）。"""
    parts = urlsplit(url)
    name = unquote(parts.path.rsplit("/", 1)[-1])
    name = re.sub(r"\.(pdf|PDF)$", "", name)
    return name.replace("-", " ").replace("_", " ")


def event_doi(event: dict) -> str | None:
    for ref in event.get("references") or []:
        doi = normalize_doi(str(ref))
        if doi:
            return doi
    for source in event.get("sources") or []:
        doi = normalize_doi(str(source.get("url") or ""))
        if doi:
            return doi
    return None


def load_events(db: Path, ids: list[str]) -> dict[str, dict]:
    if not db.exists():
        raise SystemExit(f"找不到语料库：{db}（先复制 intel-data-b 到 work/b-corpus）")
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "select id, doc from events where id in (%s)" % ",".join("?" * len(ids)),
            ids,
        ).fetchall()
    finally:
        conn.close()
    return {row["id"]: json.loads(row["doc"]) for row in rows}


def classify(case: dict, event: dict | None) -> dict:
    value = case.get("candidate_value") or {}
    url = str(value.get("pdf_url") or "")
    doi_url = normalize_doi(url)
    doi_event = event_doi(event or {})
    title = str((event or {}).get("title") or "")
    year_event = str((event or {}).get("published_at") or "")[:4] or None
    path_text = url_text(url)
    # 年份可能在更靠前的路径段里（例如 ".../VOL. 8 NO. 8 2025/标题.pdf"），
    # 所以整条路径都扫，而不是只看文件名。
    path_years = YEAR_RE.search(unquote(urlsplit(url).path))

    row = {
        "relation_id": case.get("relation_id"),
        "event_id": case.get("subject"),
        "pdf_url": url,
        "openalex_title": title,
        "openalex_year": year_event,
        "openalex_doi": doi_event,
        "pdf_doi": doi_url,
        "before": {"annotation": "pending_human_review", "linked_document_key": None},
    }

    if doi_url and doi_event:
        if doi_url.casefold() == doi_event.casefold():
            row.update(status="doi_match", evidence=f"DOI 逐字一致：{doi_url}", missing=None)
        else:
            row.update(status="doi_mismatch",
                       evidence=f"URL DOI {doi_url} ≠ OpenAlex DOI {doi_event}",
                       missing="DOI 不一致")
        return row

    missing: list[str] = []
    if not doi_event:
        missing.append("OpenAlex 记录缺 DOI")
    if not doi_url:
        missing.append("pdf_url 里没有 DOI")

    # 没有 DOI：用 URL 里能读出的标题 + 年份做双匹配。
    title_words = title_tokens(title)
    slug_words = title_tokens(path_text)
    # URL 里常常只截了标题的前半段，所以按"较短一侧被覆盖的比例"算，
    # 而不是拿它去除完整标题的长度——否则截断的 slug 会被误判成"读不出标题"。
    shorter = min(len(title_words), len(slug_words)) if title_words and slug_words else 0
    overlap = len(title_words & slug_words) / shorter if shorter else 0.0
    title_match = bool(title_words) and len(slug_words) >= 4 and overlap >= 0.8
    year_match = bool(path_years) and path_years.group(0) == year_event

    row.update(
        title_overlap=round(overlap, 2),
        title_match=title_match,
        url_year=path_years.group(0) if path_years else None,
        year_match=year_match,
    )
    if title_match and year_match:
        row.update(status="title_year_match",
                   evidence=f"标题重合 {overlap:.0%}，年份 {year_event} 一致",
                   missing=None)
        return row

    if title_match and not path_years:
        missing.append("URL 里没有年份，双匹配缺一项")
    elif title_match and not year_match:
        missing.append(f"年份不一致（URL {path_years.group(0)} / OpenAlex {year_event}）")
    elif not title_match:
        missing.append("URL 路径读不出标题（需抓取页面标题才能双匹配）")
    row.update(status="unknown", evidence=None, missing="；".join(missing))
    return row


def write_csv(rows: list[dict]) -> None:
    import csv

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    columns = ["relation_id", "event_id", "status", "openalex_doi", "pdf_doi",
               "title_match", "year_match", "missing", "evidence", "pdf_url"]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_doc(report: dict) -> None:
    lines = [
        "# 论文关联 21 条：前后状态表（2026-10-18）",
        "",
        "由 `tools/verify_paper_links.py` 生成，输入是",
        "`evaluation/b_relation_candidates_20261010.json` 里 `dimension=paper_link`",
        "且 `candidate_value` 有空字段的 21 条。判定规则：从 `pdf_url` 提取 DOI",
        "（末尾 `.pdf` 先剥掉）与 OpenAlex 记录逐字比对；没有 DOI 时用 URL 里能读出的",
        "标题 + 年份双匹配，两项都命中才算；其余写 `unknown` 并注明缺哪一项。",
        "",
        f"汇总：21 条里 **{report['summary'].get('doi_match', 0)} 条 DOI 逐字一致**，",
        f"**{report['summary'].get('unknown', 0)} 条 unknown**（原因逐行写在最后一列）。",
        "",
        "| 关系 ID | 事件 | 状态 | OpenAlex DOI | URL DOI | 标题匹配 | 年份匹配 | 缺失项 / 证据 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        detail = row.get("missing") or row.get("evidence") or ""
        lines.append(
            "| {rid} | {eid} | {status} | {odoi} | {pdoi} | {tm} | {ym} | {detail} |".format(
                rid=row["relation_id"],
                eid=row["event_id"],
                status=row["status"],
                odoi=row.get("openalex_doi") or "—",
                pdoi=row.get("pdf_doi") or "—",
                tm={True: "是", False: "否"}.get(row.get("title_match"), "—"),
                ym={True: "是", False: "否"}.get(row.get("year_match"), "—"),
                detail=detail,
            )
        )
    lines += [
        "",
        "## 边界",
        "",
        "- 这一列只回答“这条 pdf_url 是否属于该 OpenAlex 记录”，**不回答**“这篇论文讲的",
        "  主题是否已被核验”。DOI 一致只说明标识符对得上，不代表内容被人工读过。",
        "- `unknown` 的 15 条里，3 条连 OpenAlex 记录本身都没有 DOI（BREL-PA-0018/0019/0020），",
        "  其余是 URL 里没有 DOI、且 URL 路径读不出可比标题；要解决只能抓取落地页标题，",
        "  本轮没有抓。",
        "- 没有改动 `evaluation/` 下的 10-10 冻结产物，也没有往任何关联表里写“已验证”。",
        "",
    ]
    OUTPUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:

    cases = json.loads(CANDIDATES.read_text(encoding="utf-8"))["cases"]
    paper = [
        case for case in cases
        if case.get("dimension") == "paper_link"
        and any(
            str(value) in ("None", "", "unknown")
            for value in (case.get("candidate_value") or {}).values()
        )
    ]
    events = load_events(DEFAULT_DB, [case["subject"] for case in paper])
    rows = [classify(case, events.get(case["subject"])) for case in paper]
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    report = {
        "generated_at": sqlite3.connect(":memory:").execute(
            "select strftime('%Y-%m-%dT%H:%M:%SZ','now')").fetchone()[0],
        "candidate_file": str(CANDIDATES.relative_to(ROOT)),
        "database": str(DEFAULT_DB.relative_to(ROOT)),
        "rule": (
            "DOI 逐字比对（剥离 URL 的 .pdf 后缀）；无 DOI 时标题+年份双匹配，"
            "两项都命中才算；否则 unknown 并写明缺哪一项。"
        ),
        "total": len(rows),
        "summary": summary,
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    write_csv(rows)
    write_doc(report)
    print(json.dumps({"total": report["total"], "summary": summary},
                     ensure_ascii=False))
    for row in rows:
        print(f"{row['relation_id']} | {row['status']:<16} | "
              f"{row.get('missing') or row.get('evidence')}")
    print(f"\noutput: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
