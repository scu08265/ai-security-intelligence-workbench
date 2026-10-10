"""Diagnose the mid-frequency technical-term retrieval regression.

Reproduces the failing case in
``tests/test_rag_mixed_language_query.py::test_mid_frequency_technical_terms_can_carry_a_query``
and reports *which layer* drops the expected document, so the fix targets the
right place instead of guessing:

1. query tokenisation / expansion
2. the discriminative-term guard inside ``retrieve_chunks``
3. BM25 ranking (retrieved, but not cited)
4. the citation layer in ``answer_with_rag``

The corpus lives outside this repository, so point the script at it (the path
below is a Windows path; pass --corpus-dir to override)::

    python tools/diagnose_rag_midfreq.py --corpus-dir <corpus dir>

The script copies the database and never writes to the source corpus.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, rag, rag_corpus, storage  # noqa: E402

DEFAULT_CORPUS = Path("D:/ICT/intel-data-b")

CASES = (
    ("kernel-level 在哪些文档中出现？", "paper:2609.28915"),
    ("multi-agent 主题出现在哪些论文中？", "paper:2609.28900"),
)

EXPANSION_TRACKED = ("paper", "study", "arxiv", "title", "model", "models",
                     "detect", "attack", "risk", "asset")


def _banner(text: str) -> None:
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def _point_at(root: Path) -> None:
    config.DATA_DIR = root
    config.SNAPSHOT_DIR = root / "snapshots"
    config.DB_PATH = root / "intel.sqlite"
    config.ensure_dirs()
    storage.init_db()


def _key_by_document_id() -> dict[str, str]:
    with storage.connect() as conn:
        return {row["id"]: row["document_key"]
                for row in conn.execute("SELECT id, document_key FROM rag_documents").fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args()

    source_db = args.corpus_dir / "intel.sqlite"
    if not source_db.is_file():
        print("corpus not found:", source_db)
        print("run this on the machine that holds the B corpus, or pass --corpus-dir")
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="rag-midfreq-"))
    (workdir / "snapshots").mkdir()
    shutil.copy2(source_db, workdir / "intel.sqlite")
    _point_at(workdir)
    print("corpus copy:", workdir)

    records = rag_corpus.list_chunk_records(current_only=True)
    chunks = rag.chunks_from_records(records)
    n = len(chunks)
    keys = _key_by_document_id()

    _banner("1. corpus and document frequency")
    print("chunks:", n)
    doc_terms = [rag.terms(" ".join((c.title, c.text))) for c in chunks]
    token_sets = [set(t) for t in doc_terms]
    threshold = max(1, n // 10)
    print("guard threshold   : df <= len(chunks)//10 =", threshold,
          "(", round(threshold / n * 100, 1), "% )")
    interesting = sorted(set(rag.terms("kernel-level")) | set(rag.terms("multi-agent")))
    for term in sorted({t for t in interesting if t} | set(EXPANSION_TRACKED)):
        df = sum(1 for s in token_sets if term in s)
        pct = df / n * 100 if n else 0.0
        mark = "  <-- ubiquitous, cannot carry a query alone" if df > threshold else ""
        print("  %-14s df=%-5d %5.1f%%%s" % (term, df, pct, mark))

    verdicts = []
    for question, expected in CASES:
        _banner("2. query: " + question)
        print("expected document:", expected)

        query_terms = rag.terms(question)
        unique = set(query_terms)
        injected = sorted(unique & set(EXPANSION_TRACKED))
        print("unique query terms:", len(unique))
        print("expansion-injected:", injected or "none")

        expected_hits = [c for c in chunks if keys.get(c.document_id) == expected]
        print("chunks of the expected document:", len(expected_hits))
        for chunk in expected_hits[:3]:
            token_set = set(rag.terms(" ".join((chunk.title, chunk.text))))
            matched = tuple(sorted(unique & token_set))
            print("   len(text)=%-6d matched=%s" % (len(chunk.text.strip()), list(matched)))
            if len(unique) >= 4 and len(matched) < 2:
                if len(matched) == 0:
                    print("      guard: matched==0 -> dropped")
                else:
                    only = matched[0]
                    df = sum(1 for s in token_sets if only in s)
                    outcome = "PASSES" if df <= threshold else "DROPPED (df %d > %d)" % (df, threshold)
                    print("      guard: single match %r df=%d -> %s" % (only, df, outcome))
            else:
                print("      guard: not applicable (len(matched)=%d, len(unique)=%d)"
                      % (len(matched), len(unique)))

        retrieved = rag.retrieve_chunks(question, chunks, limit=8)
        retrieved_keys = [keys.get(hit.chunk.document_id) for hit in retrieved]
        print("retrieve_chunks returned:", retrieved_keys)

        answer = rag.answer_with_rag(question, [], chunks=records)
        cited = [keys.get(c["document_id"]) for c in answer["citations"]]
        print("answer_with_rag cited   :", cited)

        if expected in cited:
            print("RESULT: expected document IS cited -> this case passes here")
            verdicts.append((question, "passes"))
        elif expected in retrieved_keys:
            print("RESULT: retrieved but NOT cited -> failure is in the citation layer")
            verdicts.append((question, "citation-layer"))
        else:
            print("RESULT: not retrieved -> failure is in retrieve_chunks (guard or ranking)")
            verdicts.append((question, "retrieval"))

    _banner("3. verdict")
    for question, where in verdicts:
        print("  %-40s -> %s" % (question[:40], where))
    print()
    print("retrieval + single matched term with df > threshold")
    print("    -> recalibrate the guard for this corpus size")
    print("expansion-injected terms present")
    print("    -> the guard is being bypassed and the ranking is diluted")
    print("citation-layer")
    print("    -> fix answer_with_rag, leave retrieve_chunks alone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
