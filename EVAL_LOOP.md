# Eval System + Autonomy Plan

## What the eval system scores today

Each audit report is scored across four dimensions. Scores are 0–10 per dimension, aggregated to a single report score.

| Dimension | What it measures | Source of truth |
|---|---|---|
| **Pillar coverage** | Are exactly 2 experiments per pillar present? Correct pillar labels? | Regex parse of report markdown |
| **Evidence quality** | Does every experiment cite a real URL or artifact path that resolves (or maps logically to the store)? | URL existence check + pattern match |
| **Specificity** | Are KPIs, decision rules, and lift ranges concrete and non-generic? | LLM judge prompt against rubric |
| **Technical check completeness** | Are all 15 checks present with Pass/Warn/Fail? Do statuses match crawl data? | Structured parse + crawl data diff |

The eval runs as a Python script (`eval/score_report.py`) that accepts any `sample_output/*.md` and returns a JSON score object. It is store-agnostic by design — it never hard-codes expected content, only structural and logical rules.

## How it works today

1. **Crawl snapshot**: After each audit, the harness saves raw crawl data (HTTP status codes, robots.txt, any fetched page text) to `eval/snapshots/{store}/`.
2. **Score report**: `eval/score_report.py` parses the report markdown, extracts experiments, checks pillar distribution, validates cited URLs against the crawl snapshot, and calls the Claude API for specificity scoring using a rubric prompt.
3. **Diff against baseline**: For gingerpeople.com, the diff runs against `target_report.md`. For new stores, the baseline is the previous audit run — regression is flagged if score drops > 10%.

## How this becomes autonomous and self-learning (1–3 months)

**Month 1 — Ground truth accumulation**

The weakest part of any eval is the rubric. The LLM judge prompt is the current rubric; it needs calibration. Fix: after each audit, a human reviewer takes 10 minutes to annotate which experiments they'd actually ship (binary: yes/no). Those annotations feed a labeled dataset. By run 10–15, there's enough signal to retrain or fine-tune the judge prompt via few-shot examples from the labeled set. Human annotation surface shrinks from full-report review to yes/no per experiment — 10 min → 3 min per report.

**Month 2 — Automated regression detection**

Once the judge is calibrated, the eval loop runs without humans in the normal case. The trigger for human entry is a score drop > 10% from the previous run on the same store, or a new store type that scores below 6/10 overall. Both cases email a reviewer with the diff and a "approve / fix prompt" button. The system learns from every approved audit: the approved report is added to the few-shot examples, improving future judge quality without a separate training step.

**Month 3 — Self-improving prompts**

The harness prompt that drives the Reason phase (the 10-experiment generation) is versioned. The eval system tracks which prompt version produced which score. When a new prompt variant is tested, it runs on 3 historical stores (gingerpeople, zenrojas, and a third held-out store) and is auto-promoted if it scores higher on all three with no regression on specificity. Prompt iteration becomes a closed loop: the eval scores a new variant → auto-promote or reject → no human needed unless the held-out store is new.

## Where humans enter — and how that surface shrinks

| Stage | Human role today | How it shrinks |
|---|---|---|
| Rubric calibration | Annotate 10–15 reports | Stops after labeled dataset reaches 50 examples |
| Score anomaly review | Approve/reject flagged low-score reports | Threshold auto-tightens as false-positive rate drops |
| New store type | Review first report for unseen verticals | Judge prompt gets vertical-specific few-shot examples after 2 approved audits per vertical |
| Prompt versioning | None — auto-promoted | Stays automated; human only if held-out score drops > 15% |

The steady-state is: humans see one email per 8–12 audits (score anomalies only). Everything else runs unattended.
