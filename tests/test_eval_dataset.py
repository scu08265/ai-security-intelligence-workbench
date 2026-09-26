from app.eval_dataset import load_cases, run_labelled_evaluation, score_records


def test_dataset_provenance_is_explicit_and_mixed():
    cases = load_cases()
    assert {case["provenance"] for case in cases} == {"real_verified", "synthetic_regression"}
    assert all(case.get("source_ref") for case in cases)


def test_metrics_keep_separate_denominators():
    gold = [
        {"id": "a", "provenance": "real_verified", "expected_event_ids": ["E1"],
         "required_answer_terms": ["fixed"], "expected_evidence_ids": ["S1"], "should_refuse": False},
        {"id": "b", "provenance": "synthetic_regression", "expected_event_ids": [],
         "required_answer_terms": [], "expected_evidence_ids": [], "should_refuse": True},
    ]
    result = score_records(gold, {
        "a": {"event_ids": ["E1", "E2"], "answer": "fixed", "evidence_ids": ["S1"], "refused": False},
        "b": {"event_ids": [], "answer": "", "evidence_ids": [], "refused": True},
    })
    assert result["retrieval_precision"] == 0.5
    assert result["retrieval_recall"] == 1.0
    assert result["answer_accuracy"] == 1.0
    assert result["citation_accuracy"] == 1.0
    assert result["refusal_accuracy"] == 1.0


def test_labelled_runner_measures_all_five_metrics():
    result = run_labelled_evaluation([], [])
    for key in ("retrieval_precision", "retrieval_recall", "answer_accuracy",
                "citation_accuracy", "refusal_accuracy"):
        assert key in result
    assert result["counts"]["refusal_cases"] > 0
