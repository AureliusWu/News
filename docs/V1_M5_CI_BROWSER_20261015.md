# M5 isolated CI first-run evidence, 2026-10-15

## Outcome

**NOT PASSED. V1.0.0 is not released.**

Infrastructure commit: `39914e12e51586f8ef88242c635835d5f5e8b9b6`.
[Run 38706750587](https://github.com/AureliusWu/News/actions/runs/38706750587)
was created at `2026-10-15T08:35:26Z` and finished with failure at
`2026-10-15T08:36:27Z`. The job is terminal, not waiting or still running.

| Stage | Actual result |
| --- | --- |
| Checkout, Node setup and dependency installation | Passed |
| Install Chromium and Firefox engines | Passed |
| Freeze public inputs and build comparison clients | Failed during input validation, before builds |
| Browser functional/offline/upgrade tests | Not run |
| Same-input Lighthouse comparison | Not run |
| Artifact upload step | Step succeeded, but found no files; no artifact was uploaded |
| Pages deployment | Not part of this manual workflow; not triggered by this work |

Installing browser engines does not prove that either browser launched or that
any browser acceptance test passed. The upload step's green status does not prove
that an artifact exists. The failure log and API metadata are now preserved in
this repository separately.

## Verified test-harness defect

The new `prepare.mjs` incorrectly applied the event asset's top-level binding
fields to the source-health report as well. It expected `generated_at` and
`content_sha256` on both documents. The source-health schema has neither field.

The production responses inspected after the failure both returned HTTP 200:

| Field | News | Bound source-health report |
| --- | --- | --- |
| `snapshot_id` | `35b7edde202b3e2dcaf1c299` | `35b7edde202b3e2dcaf1c299` |
| Generation/check time | `generated_at=2026-10-15T07:58:18.169271Z` | `checked_at=2026-10-15T07:58:18.169271Z` |
| Content hash | `dbe53f1a35d6ac4380bcbcf694dde17d33784e6af78330873db3d9df000d3c4f` | No such schema field |
| Article count | 806 | `summary.article_count=806` |
| Health gate | `health.gate_pass=true` | `summary.gate_pass=true` |

Thus the observed failure is a defect in the newly added verification harness,
not evidence of a mismatched production generation. The actual failure message
was `Mismatched frozen asset source-health.35b7edde202b3e2dcaf1c299.json: generated_at`.

Proposed correction, **not applied yet**: preserve strict event binding checks;
validate source-health using its actual snapshot ID, `checked_at`, summary and
health contract; retain byte-for-byte frozen-input hashes for both builds. Do not
change production schemas, acceptance thresholds or original failure records.
Approval to repair this introduced harness defect was requested and remains
pending; an automatic goal continuation is not treated as human approval.

## Independent scheduling audit

Queried GitHub Actions API at `2026-10-15T08:39:51.962Z`. Both workflows were
reported `active`. The inspected closed seven-day window is
`2026-10-08T08:30:00Z` through `2026-10-15T08:30:00Z`, with 336 expected
half-hour slots. Each API history page reached beyond the start of this window.

| Workflow | All runs in window | Scheduled runs | Scheduled-run creation slots | Maximum scheduled creation gap |
| --- | --- | --- | --- | --- |
| `deploy-gh-pages.yml` | 36: 32 scheduled, 3 push, 1 manual | 32, all successful | 32 | 10.022222 hours |
| `observe-news.yml` | 32: 31 scheduled, 1 manual | 31, all successful | 31 | 9.418889 hours |

These are workflow-creation and conclusion statistics, **not** freshness-gate
passing-slot counts. A green run alone proves neither a published fresh snapshot
nor a complete, generation-bound observation. The audit establishes sparse
created-run coverage; it does not by itself establish why particular scheduled
runs were absent or delayed. Missing history is not backfilled or synthesized.

This audit does not rerun or replace the last full freshness calculation. That
earlier calculation had 16/336 passing slots (4.76%) in its distinct window ending
`2026-10-15T08:00:00Z`, and was FAIL. Do not relabel it as the newer audit window.

## Evidence

- [Failed step log](evidence/v1-m5-ci-browser-20261015/run-38706750587-failed.log)
- [GitHub run metadata](evidence/v1-m5-ci-browser-20261015/run-38706750587.json)
- [Production field diagnostic](evidence/v1-m5-ci-browser-20261015/binding-diagnostic.json)
- [Scheduling audit and retained run records](evidence/v1-m5-ci-browser-20261015/schedule-audit.json)
- [Original fixed-scope CI plan](V1_M5_CI_BROWSER_PLAN_20261015.md)

## Still open

- Repair approval, then an actual CI browser/offline/upgrade/comparison run.
- Production seven-day freshness and stable independent observation cadence.
- Public mobile first-screen tail and real interaction performance.
- Physical-phone evidence and the complete legacy-client upgrade matrix.
- Previously blocked Windows start/stop and fault-injection acceptance.
- Final version, tag, formal release and post-release acceptance.

The application remains `0.9.0-alpha.1 / M5-candidate`, not a completed V1.0.0.
The ambiguous phone reply is not accepted as device/browser/operation evidence.
Cloudflare remains deferred. This documentation work does not change application
code, clear user storage, start local browser/server processes or deploy a site.
