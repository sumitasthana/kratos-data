"""
quality_engine.py — Kratos Data Quality Metrics Layer
======================================================
Computes six FDIC-relevant quality dimensions on in-memory row dicts:
  Completeness · Accuracy · Consistency · Validity · Uniqueness · Timeliness

No extra runtime dependencies required (pyyaml is optional; falls back to
hard-coded defaults if the config file cannot be loaded).
"""

import os
import re
from datetime import date
from typing import Any

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: dict[str, Any] = {
    "completeness_threshold_pct": 95.0,
    "accuracy_threshold_pct":     98.0,
    "validity_threshold_pct":     99.0,
    "uniqueness_max_dup_pct":      0.0,
    "timeliness_sla_days":        30,
}


def _load_config() -> dict[str, Any]:
    cfg_path = os.path.join(os.path.dirname(__file__), "quality_config.yaml")
    try:
        import yaml  # type: ignore
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
            return {**_DEFAULT_CONFIG, **loaded}
    except Exception:
        pass
    return dict(_DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# Static reference sets
# ---------------------------------------------------------------------------

_VALID_PARTY_TYPES   = {"Individual", "Organization", "Government"}
_VALID_PARTY_STATUS  = {"Active", "Inactive", "Deceased", "Dissolved"}
_VALID_ACCOUNT_TYPES = {
    "Savings",
    "Checking",
    "Money Market",
    "Certificate of Deposit",
    "Individual Retirement Account",
    "Trust Account",
    "Government Account",
    "Business Account",
    "Escrow Account",
    "Sweep Account",
    "Other",
}
_VALID_ACCOUNT_STATUS = {"Active", "Closed", "Frozen", "Dormant"}

_UUID_RE    = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
_DATE_RE    = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ORC_RE     = re.compile(r"^[A-Za-z0-9_]+$")  # non-empty ORC codes are alphanumeric+underscore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_blank(val: Any) -> bool:
    return val is None or str(val).strip() in ("", "None", "null", "NULL")


def _dim(name: str, status: str, value: str, threshold: str, details: list) -> dict:
    return {
        "name":      name,
        "status":    status,   # "pass" | "warn" | "fail"
        "value":     value,
        "threshold": threshold,
        "details":   details,
    }


# ---------------------------------------------------------------------------
# Dimension functions
# ---------------------------------------------------------------------------

def _check_completeness(rows: list[dict], n: int, cfg: dict) -> dict:
    threshold = cfg["completeness_threshold_pct"]
    all_cols  = list(rows[0].keys()) if rows else []
    total     = n * len(all_cols) or 1

    null_cells   = 0
    flagged_cols = []
    for col in all_cols:
        col_nulls = sum(1 for r in rows if _is_blank(r.get(col)))
        null_cells += col_nulls
        pct_null = (col_nulls / n) * 100
        if pct_null > (100 - threshold):
            flagged_cols.append({
                "column": col,
                "recommendation": (
                    f"Column `{col}` has {round(pct_null, 1)}% null/empty values "
                    f"— exceeds the {100 - threshold:.0f}% null tolerance. "
                    f"Check upstream source query or add a NOT NULL constraint to the generation pipeline."
                ),
            })

    overall_pct = round(((total - null_cells) / total) * 100, 1)
    if overall_pct < threshold:
        status = "fail"
    elif flagged_cols:
        status = "warn"
    else:
        status = "pass"

    return _dim(
        "Completeness",
        status,
        f"{overall_pct}%",
        f">= {threshold}%",
        flagged_cols,
    )


def _check_accuracy(rows: list[dict], n: int, cfg: dict) -> dict:
    threshold = cfg["accuracy_threshold_pct"]
    checks    = []

    bad_pt = sum(
        1 for r in rows
        if not _is_blank(r.get("party_type")) and r["party_type"] not in _VALID_PARTY_TYPES
    )
    if bad_pt:
        checks.append({
            "column": "party_type",
            "recommendation": (
                f"{bad_pt} rows have `party_type` outside the valid set "
                f"{{Individual, Organization, Government}} — verify the party_type enum mapping "
                f"in orc_engine.py."
            ),
        })

    bad_ps = sum(
        1 for r in rows
        if not _is_blank(r.get("party_status")) and r["party_status"] not in _VALID_PARTY_STATUS
    )
    if bad_ps:
        checks.append({
            "column": "party_status",
            "recommendation": (
                f"{bad_ps} rows have `party_status` outside {{Active, Inactive, Deceased, Suspended}} "
                f"— review the party_status transition logic."
            ),
        })

    bad_at = sum(
        1 for r in rows
        if not _is_blank(r.get("account_type")) and r["account_type"] not in _VALID_ACCOUNT_TYPES
    )
    if bad_at:
        checks.append({
            "column": "account_type",
            "recommendation": (
                f"{bad_at} rows have `account_type` not in the defined valid set "
                f"— confirm the AccountType enum covers all product codes."
            ),
        })

    bad_as = sum(
        1 for r in rows
        if not _is_blank(r.get("account_status")) and r["account_status"] not in _VALID_ACCOUNT_STATUS
    )
    if bad_as:
        checks.append({
            "column": "account_status",
            "recommendation": (
                f"{bad_as} rows have `account_status` outside {{Active, Closed, Frozen, Dormant, PendingClosure}} "
                f"— check status transition guards in the account model."
            ),
        })

    bad_bal = 0
    for r in rows:
        try:
            float(r.get("current_balance", "0") or "0")
        except (ValueError, TypeError):
            bad_bal += 1
    if bad_bal:
        checks.append({
            "column": "current_balance",
            "recommendation": (
                f"{bad_bal} rows have `current_balance` values that cannot be parsed as a decimal number "
                f"— investigate non-numeric characters in the balance column."
            ),
        })

    total_field_checks = 5 * n or 1
    total_failures     = bad_pt + bad_ps + bad_at + bad_as + bad_bal
    pct                = round(((total_field_checks - total_failures) / total_field_checks) * 100, 1)

    if pct < threshold:
        status = "fail"
    elif checks:
        status = "warn"
    else:
        status = "pass"

    return _dim("Accuracy", status, f"{pct}%", f">= {threshold}%", checks)


def _check_consistency(rows: list[dict], n: int, _cfg: dict) -> dict:
    today      = date.today()
    violations = []

    future = [
        r for r in rows
        if r.get("account_open_date") and _DATE_RE.match(str(r["account_open_date"]))
        and date.fromisoformat(str(r["account_open_date"])) > today
    ]
    if future:
        violations.append({
            "rule": "future_open_date",
            "recommendation": (
                f"{len(future)} records have `account_open_date` set in the future "
                f"— add a validation rule in the generation config to cap open dates at today ({today})."
            ),
        })

    blank_names = sum(
        1 for r in rows
        if str(r.get("name", "")).strip() in ("", "Unknown")
    )
    if blank_names:
        violations.append({
            "rule": "blank_or_placeholder_name",
            "recommendation": (
                f"{blank_names} records have a blank or 'Unknown' `name` "
                f"— check the COALESCE fallback logic in _GENERATE_SQL for parties missing both "
                f"individual_name and organization_legal_name."
            ),
        })

    status = "fail" if violations else "pass"
    return _dim(
        "Consistency",
        status,
        f"{len(violations)} violation{'s' if len(violations) != 1 else ''}",
        "0 violations",
        violations,
    )


def _check_validity(rows: list[dict], n: int, cfg: dict) -> dict:
    threshold = cfg["validity_threshold_pct"]
    details   = []

    bad_pid = sum(
        1 for r in rows
        if r.get("party_id") and not _UUID_RE.match(str(r["party_id"]))
    )
    if bad_pid:
        details.append({
            "column": "party_id",
            "recommendation": (
                f"{bad_pid} `party_id` values do not match UUID format "
                f"— ensure party_id::text casts are emitting standard hyphenated UUIDs."
            ),
        })

    bad_aid = sum(
        1 for r in rows
        if r.get("account_id") and not _UUID_RE.match(str(r["account_id"]))
    )
    if bad_aid:
        details.append({
            "column": "account_id",
            "recommendation": (
                f"{bad_aid} `account_id` values do not match UUID format "
                f"— confirm account_id is a proper UUID primary key."
            ),
        })

    bad_date = sum(
        1 for r in rows
        if r.get("account_open_date") and not _DATE_RE.match(str(r["account_open_date"]))
    )
    if bad_date:
        details.append({
            "column": "account_open_date",
            "recommendation": (
                f"{bad_date} `account_open_date` values are not in ISO-8601 (YYYY-MM-DD) format "
                f"— add an explicit TO_CHAR or ::date cast in the generation SQL."
            ),
        })

    bad_orc = sum(
        1 for r in rows
        if r.get("orc_code") and str(r["orc_code"]).strip()
        and not _ORC_RE.match(str(r["orc_code"]).strip())
    )
    if bad_orc:
        details.append({
            "column": "orc_code",
            "recommendation": (
                f"{bad_orc} non-empty `orc_code` values contain unexpected characters "
                f"— validate against the OrcCodeEnum label set."
            ),
        })

    total_checks = 4 * n or 1
    total_fails  = bad_pid + bad_aid + bad_date + bad_orc
    pct          = round(((total_checks - total_fails) / total_checks) * 100, 1)

    if pct < threshold:
        status = "fail"
    elif details:
        status = "warn"
    else:
        status = "pass"

    return _dim("Validity", status, f"{pct}%", f">= {threshold}%", details)


def _check_uniqueness(rows: list[dict], n: int, cfg: dict) -> dict:
    max_dup_pct = cfg["uniqueness_max_dup_pct"]
    account_ids = [r.get("account_id") for r in rows if r.get("account_id")]
    dup_count   = len(account_ids) - len(set(account_ids))
    dup_pct     = round((dup_count / n) * 100, 2) if n else 0.0

    details = []
    if dup_count > 0:
        details.append({
            "column": "account_id",
            "recommendation": (
                f"{dup_count} duplicate rows detected on `account_id` ({dup_pct}%) "
                f"— add a DISTINCT clause or a deduplication step after the generation JOIN."
            ),
        })

    status = "fail" if dup_pct > max_dup_pct else "pass"
    return _dim(
        "Uniqueness",
        status,
        f"{dup_pct}% duplicates",
        "0% duplicates",
        details,
    )


def _check_timeliness(rows: list[dict], n: int, cfg: dict) -> dict:
    sla_days   = int(cfg["timeliness_sla_days"])
    today      = date.today()
    latest     = None

    for r in rows:
        d_str = r.get("account_open_date", "")
        if d_str and _DATE_RE.match(str(d_str)):
            try:
                d = date.fromisoformat(str(d_str))
                if latest is None or d > latest:
                    latest = d
            except ValueError:
                pass

    if latest is None:
        return _dim(
            "Timeliness",
            "warn",
            "unknown",
            f"<= {sla_days} days",
            [{"recommendation": "No valid `account_open_date` found — cannot assess data freshness."}],
        )

    delta = (today - latest).days
    if delta > sla_days:
        status  = "warn"
        details = [{
            "column": "account_open_date",
            "recommendation": (
                f"Most recent record is {delta} days old, exceeding the {sla_days}-day SLA "
                f"— verify the upstream ingestion job ran successfully and the DB is up to date."
            ),
        }]
    else:
        status  = "pass"
        details = []

    return _dim(
        "Timeliness",
        status,
        f"{delta} day{'s' if delta != 1 else ''} since latest record",
        f"<= {sla_days} days",
        details,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_quality(rows: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    """
    Run all six quality dimensions against *rows* (list of column-keyed dicts).
    Returns a serialisable report dict ready for JSON responses and CSV headers.
    """
    n = len(rows)
    if n == 0:
        return {
            "overall":      "warn",
            "dimensions":   [],
            "summary_line": "No rows to evaluate",
            "generated_at": generated_at,
            "row_count":    0,
        }

    cfg = _load_config()

    dimensions = [
        _check_completeness(rows, n, cfg),
        _check_accuracy(rows, n, cfg),
        _check_consistency(rows, n, cfg),
        _check_validity(rows, n, cfg),
        _check_uniqueness(rows, n, cfg),
        _check_timeliness(rows, n, cfg),
    ]

    fail_count = sum(1 for d in dimensions if d["status"] == "fail")
    warn_count = sum(1 for d in dimensions if d["status"] == "warn")

    if fail_count > 0:
        overall = "fail"
    elif warn_count > 0:
        overall = "warn"
    else:
        overall = "pass"

    parts = []
    if fail_count:
        parts.append(f"{fail_count} failure{'s' if fail_count != 1 else ''}")
    if warn_count:
        parts.append(f"{warn_count} warning{'s' if warn_count != 1 else ''}")
    summary_line = ", ".join(parts) if parts else "All checks passed"

    return {
        "overall":      overall,
        "dimensions":   dimensions,
        "summary_line": summary_line,
        "generated_at": generated_at,
        "row_count":    n,
    }


def quality_csv_header(report: dict[str, Any]) -> str:
    """
    Return commented metadata lines to prepend to a CSV download.
    Each line begins with '#' so standard CSV parsers treat it as a comment.
    """
    icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
    lines = [
        "# Kratos Data Export",
        f"# Generated: {report.get('generated_at', '')}",
        f"# Rows: {report.get('row_count', 0)}",
        "#",
        "# --- Data Quality Report ---",
    ]
    for d in report.get("dimensions", []):
        lines.append(
            f"# {d['name']:<14} {d['value']:<30} threshold: {d['threshold']:<20} [{icon.get(d['status'], d['status'])}]"
        )
    lines.append(
        f"# Overall: {icon.get(report.get('overall',''), report.get('overall','').upper())} "
        f"— {report.get('summary_line', '')}"
    )
    lines.append("#")
    return "\n".join(lines) + "\n"
