#!/usr/bin/env python3
"""
Qosmic Audit Report Scorer
Usage: python eval/score_report.py <path-to-report.md>

Scores any audit report on 4 dimensions (0-10 each):
  1. pillar_coverage   — exactly 2 experiments per pillar
  2. evidence_quality  — every experiment cites a real URL or artifact path
  3. specificity       — KPI, decision rule, lift range, confidence % all present and concrete
  4. tech_checks       — all 15 standard checks present with Pass/Warn/Fail statuses
"""

import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

PILLARS = {"conversion", "aov", "retention", "acquisition", "performance"}

REQUIRED_TECH_CHECKS = [
    "ssl",
    "https",
    "sitemap",
    "robots",
    "critical pages",
    "meta tags",
    "structured data",
    "favicon",
    "mobile",
    "page speed mobile",
    "page speed desktop",
    "broken links",
    "image",
    "cookie",
    "checkout",
]

VALID_STATUSES = {"pass", "warn", "fail"}


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_experiments(text: str) -> list[dict]:
    """Extract each experiment block as a dict of fields."""
    experiments = []
    # Split on experiment headings (### exp-...)
    blocks = re.split(r"(?=###\s+exp-)", text, flags=re.IGNORECASE)
    for block in blocks:
        if not block.strip().startswith("###"):
            continue
        exp = {}
        # Title line
        title_match = re.match(r"###\s+(.+)", block)
        exp["title"] = title_match.group(1).strip() if title_match else ""
        # Named fields: **Field:** value (possibly multiline until next **)
        field_pattern = re.compile(
            r"\*\*(Pillar|Affected surface|URL|Evidence|Hypothesis|Primary change|"
            r"Primary KPI|Decision rule|Expected lift|Confidence):\*\*\s*(.+?)(?=\n\*\*|\Z)",
            re.DOTALL | re.IGNORECASE,
        )
        for m in field_pattern.finditer(block):
            key = m.group(1).strip().lower().replace(" ", "_")
            val = m.group(2).strip().replace("\n", " ")
            exp[key] = val
        experiments.append(exp)
    return experiments


def parse_tech_checks(text: str) -> list[dict]:
    """Extract rows from the Technical checks table."""
    checks = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if "| check" in stripped.lower() and "status" in stripped.lower():
            in_table = True
            continue
        if in_table:
            if not stripped.startswith("|"):
                in_table = False
                continue
            if re.match(r"\|[\s\-|]+\|", stripped):
                continue  # separator row
            cols = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cols) >= 2:
                checks.append({"check": cols[0], "status": cols[1], "detail": cols[2] if len(cols) > 2 else ""})
    return checks


# ── Scorers ───────────────────────────────────────────────────────────────────

def score_pillar_coverage(experiments: list[dict]) -> tuple[float, list[str]]:
    """2 experiments per pillar = 10. Deduct 2 per missing or over-represented pillar."""
    issues = []
    counts: dict[str, int] = {p: 0 for p in PILLARS}

    for exp in experiments:
        pillar = exp.get("pillar", "").strip().lower()
        if pillar in counts:
            counts[pillar] += 1
        else:
            issues.append(f"Unknown pillar '{pillar}' in experiment: {exp.get('title', '?')[:60]}")

    deductions = 0
    for pillar, count in counts.items():
        if count == 0:
            issues.append(f"Pillar '{pillar}' has 0 experiments (need 2)")
            deductions += 2
        elif count == 1:
            issues.append(f"Pillar '{pillar}' has 1 experiment (need 2)")
            deductions += 1
        elif count > 2:
            issues.append(f"Pillar '{pillar}' has {count} experiments (need exactly 2)")
            deductions += count - 2

    total_exps = len(experiments)
    if total_exps != 10:
        issues.append(f"Found {total_exps} experiments (need exactly 10)")
        deductions += abs(total_exps - 10)

    score = max(0.0, 10.0 - deductions)
    return score, issues


def score_evidence_quality(experiments: list[dict]) -> tuple[float, list[str]]:
    """Every experiment needs an Evidence field with a URL or path. Score = % with valid evidence * 10."""
    issues = []
    url_pattern = re.compile(r"https?://[^\s]+")
    path_pattern = re.compile(r"/[a-zA-Z0-9_\-/.]+")

    valid = 0
    for exp in experiments:
        evidence = exp.get("evidence", "") or exp.get("url", "")
        title = exp.get("title", "?")[:50]
        if not evidence:
            issues.append(f"No evidence field in: {title}")
            continue
        has_url = bool(url_pattern.search(evidence))
        has_path = bool(path_pattern.search(evidence))
        if has_url or has_path:
            valid += 1
        else:
            issues.append(f"Evidence has no URL or path in: {title}")

    if not experiments:
        return 0.0, ["No experiments found"]

    score = round((valid / len(experiments)) * 10, 1)
    return score, issues


def score_specificity(experiments: list[dict]) -> tuple[float, list[str]]:
    """
    Each experiment should have:
    - primary_kpi: non-empty, not generic
    - decision_rule: non-empty, contains a measurable condition
    - expected_lift: contains % or numbers
    - confidence: contains %

    Score = average completeness across all experiments * 10
    """
    issues = []
    generic_kpis = {"conversion rate", "revenue", "sales", "traffic", "engagement"}
    lift_pattern = re.compile(r"\d+")
    confidence_pattern = re.compile(r"\d+\s*%")

    total_fields = 0
    filled_fields = 0

    for exp in experiments:
        title = exp.get("title", "?")[:50]

        # KPI
        total_fields += 1
        kpi = exp.get("primary_kpi", "").lower().strip()
        if kpi and kpi not in generic_kpis and len(kpi) > 5:
            filled_fields += 1
        else:
            issues.append(f"Missing or generic primary_kpi in: {title}")

        # Decision rule
        total_fields += 1
        rule = exp.get("decision_rule", "").strip()
        if rule and len(rule) > 20:
            filled_fields += 1
        else:
            issues.append(f"Missing or too-short decision_rule in: {title}")

        # Expected lift
        total_fields += 1
        lift = exp.get("expected_lift", "").strip()
        if lift and lift_pattern.search(lift):
            filled_fields += 1
        else:
            issues.append(f"Missing numeric expected_lift in: {title}")

        # Confidence
        total_fields += 1
        conf = exp.get("confidence", "").strip()
        if conf and confidence_pattern.search(conf):
            filled_fields += 1
        else:
            issues.append(f"Missing confidence % in: {title}")

    if total_fields == 0:
        return 0.0, ["No experiments to score"]

    score = round((filled_fields / total_fields) * 10, 1)
    return score, issues


def score_tech_checks(checks: list[dict]) -> tuple[float, list[str]]:
    """
    Score = (present standard checks / 15) * 6  +  (checks with valid status / total) * 4
    """
    issues = []
    found_checks = {c["check"].lower() for c in checks}

    # Check for each required check (fuzzy match)
    found_required = 0
    for required in REQUIRED_TECH_CHECKS:
        matched = any(required in found for found in found_checks)
        if matched:
            found_required += 1
        else:
            issues.append(f"Missing tech check: '{required}'")

    # Check status validity
    valid_status_count = 0
    for c in checks:
        status = c["status"].strip().lower()
        if status in VALID_STATUSES:
            valid_status_count += 1
        else:
            issues.append(f"Invalid status '{c['status']}' for check: {c['check']}")

    if not checks:
        return 0.0, ["No technical checks table found"]

    coverage_score = (found_required / len(REQUIRED_TECH_CHECKS)) * 6
    status_score = (valid_status_count / len(checks)) * 4
    score = round(coverage_score + status_score, 1)
    return min(10.0, score), issues


# ── Main ──────────────────────────────────────────────────────────────────────

def score_report(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")

    experiments = parse_experiments(text)
    tech_checks = parse_tech_checks(text)

    pillar_score, pillar_issues = score_pillar_coverage(experiments)
    evidence_score, evidence_issues = score_evidence_quality(experiments)
    specificity_score, specificity_issues = score_specificity(experiments)
    tech_score, tech_issues = score_tech_checks(tech_checks)

    total = round((pillar_score + evidence_score + specificity_score + tech_score) / 4, 2)

    return {
        "report": path,
        "experiments_found": len(experiments),
        "tech_checks_found": len(tech_checks),
        "scores": {
            "pillar_coverage":  pillar_score,
            "evidence_quality": evidence_score,
            "specificity":      specificity_score,
            "tech_checks":      tech_score,
            "total":            total,
        },
        "issues": {
            "pillar_coverage":  pillar_issues,
            "evidence_quality": evidence_issues,
            "specificity":      specificity_issues,
            "tech_checks":      tech_issues,
        },
    }


def print_report(result: dict):
    scores = result["scores"]
    print(f"\n{'='*60}")
    print(f"  Qosmic Audit Eval — {Path(result['report']).name}")
    print(f"{'='*60}")
    print(f"  Experiments found : {result['experiments_found']}")
    print(f"  Tech checks found : {result['tech_checks_found']}")
    print()
    print(f"  {'Dimension':<22} {'Score':>6}")
    print(f"  {'-'*30}")
    for dim, score in scores.items():
        if dim == "total":
            print(f"  {'-'*30}")
        label = dim.replace("_", " ").title()
        bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"  {label:<22} {score:>5.1f}  {bar}")
    print()

    all_issues = []
    for dim, issues in result["issues"].items():
        for issue in issues:
            all_issues.append(f"  [{dim}] {issue}")

    if all_issues:
        print("  Issues:")
        for issue in all_issues:
            print(f"    ⚠  {issue}")
    else:
        print("  No issues found.")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eval/score_report.py <report.md> [--json]")
        sys.exit(1)

    report_path = sys.argv[1]
    as_json = "--json" in sys.argv

    if not Path(report_path).exists():
        print(f"Error: file not found: {report_path}")
        sys.exit(1)

    result = score_report(report_path)

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
