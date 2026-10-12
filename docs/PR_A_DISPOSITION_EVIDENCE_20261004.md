# A: disposition closure verification and evidence

> **Environment qualifier (added 2026-10-12)**: the `4 / 3 / 0.75` below comes from the copy of
> the A machine's `data/intel.sqlite`. That database is **not present on the delivery machine**,
> so this number reads as a process-landing demo on the A machine, not as the delivery closure
> rate. The delivery baseline is the delivery machine's `data/intel.sqlite`:
> **48 high-priority / 4 closed / `closure_rate` 8.33% / `verified_rate` 6.25%**.
> See `docs/METRICS_BASELINE.md` section 3; do not mix the two in one metrics table.

## What changed

- Added an isolated API evidence runner for the remediation disposition state machine.
- Added tests for `accepted` not counting as verified, null closure rate on an empty
  denominator, and immutable `opened_at`.
- Recorded the synthetic/real asset boundary and current sample-size limitations.
- Added a short conclusion suitable for the technical report.

## Verification

- Missing assignee is rejected without creating a disposition transition.
- A still-affected version is downgraded from `verified` to `fixed` and keeps the
  failed re-verification audit record.
- A safe version is verified, closes with `closed_at`, and leaves the original
  `assessments.status=affected`.
- Closure rate moved from `0.0` to `0.75` using API-derived metrics only (A-machine scope; the
  delivery-machine closure rate is 8.33%, see the qualifier above).
- `/api/dispositions/metrics` and `/api/competition/scorecard.disposition` have
  zero field mismatches.
- Full test suite: `577 passed, 57 skipped`.

## Evidence

- `artifacts/a_eval/disposition-closure-20261004/evidence.json`
- `artifacts/a_eval/disposition-closure-20261004/state-machine-rules.csv`
- `artifacts/a_eval/disposition-closure-20261004/closure-timeline.csv`
- `artifacts/a_eval/disposition-closure-20261004/page-consistency.json`
- `docs/A_DISPOSITION_TECHNICAL_CONCLUSION.md`

## Limitations

The selected high-priority findings are synthetic `asset-cdx-*` records. The
original B database copy `D:\ICT\intel-data-b-poc-20261002` is not present on
this host, so this PR does not claim to reproduce the 27-row baseline from that
copy. Real runtime dependency assets were imported and assessed, but did not
produce high-priority affected findings. `verified` means the system re-check
passed for the current asset facts; it is not evidence of a production upgrade.
