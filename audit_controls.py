"""
audit_controls.py — FDIC Part 370 / Part 330 Audit Control Functions
=====================================================================
Implements 10 automated audit controls that validate data completeness,
regulatory compliance, and calculation accuracy.

Control catalogue:
  A1 — ORC Assignment          (FDIC Part 370 § 370.3)
  A2 — ORC Validation          (FDIC Part 370 § 370.4)
  A3 — Fiduciary Documentation (FDIC Part 370 § 370.5)
  A4 — Beneficiary Data        (FDIC Part 330 § 330.10(d))
  A5 — POD/TOD Designation     (FDIC Part 370 § 370.5)
  A6 — KYC/CIP                 (FinCEN CIP 31 U.S.C. § 5318)
  B1 — Daily Balance           (FDIC Part 370 § 360.8)
  B3 — Interest Accrual        (FDIC Part 370 § 370.4)
  C2 — Coverage Calculation    (FDIC Part 330 § 330.1)
  G1 — Annual Certification    (FDIC Part 370 § 370.3)

Python 3.11+ | SQLAlchemy 2.x async
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy Row / RowMapping to a plain dict."""
    return dict(row._mapping)


# ---------------------------------------------------------------------------
# A-Series: Account / ORC Controls
# ---------------------------------------------------------------------------

async def control_a1_orc_assignment(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control A1 — ORC Assignment Integrity.

    Fails when:
      • An active/dormant account has no ORC classification row.
      • orc_determination_date != account_open_date
        (ORC must be assigned on the day the account opens per FDIC Part 370 § 370.3).

    Regulatory: FDIC Part 370 § 370.3(b) — The bank shall maintain the information
    necessary to determine deposit insurance within 24 hours of failure; ORC must
    be assigned at account opening.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts, one per failing account, with keys:
          account_id, account_number, account_type, account_open_date,
          orc_code (NULL if missing), orc_determination_date, failure_reason.
    """
    sql = text(
        """
        SELECT
            a.account_id,
            a.account_number,
            a.account_type,
            a.account_open_date,
            arc.orc_code,
            arc.orc_determination_date,
            CASE
                WHEN arc.classification_id IS NULL        THEN 'Missing ORC classification row'
                WHEN arc.orc_code IS NULL                 THEN 'NULL orc_code'
                WHEN arc.orc_determination_date != a.account_open_date
                                                          THEN 'orc_determination_date != account_open_date'
            END AS failure_reason
        FROM account a
        LEFT JOIN account_regulatory_classification arc ON arc.account_id = a.account_id
        WHERE a.account_status IN ('Active', 'Dormant')
          AND (
              arc.classification_id IS NULL
              OR arc.orc_code IS NULL
              OR arc.orc_determination_date != a.account_open_date
          )
        ORDER BY a.account_open_date, a.account_number
        """
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


async def control_a2_orc_validation(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control A2 — ORC Validation Staleness & Consistency.

    Fails when:
      • orc_verification_date is older than 365 days (annual re-verification required).
      • is_joint_ownership = TRUE but fewer than 2 active ownership rows exist.
      • is_trust = TRUE but no fiduciary_arrangement row exists.

    Regulatory: FDIC Part 370 § 370.4(c) — Ownership Right & Capacity must be
    re-verified to ensure continued accuracy.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          account_id, account_number, orc_code, orc_verification_date,
          is_joint_ownership, owner_count, is_trust, has_fiduciary, failure_reason.
    """
    stale_cutoff = date.today() - timedelta(days=365)
    sql = text(
        """
        WITH owner_counts AS (
            SELECT account_id, COUNT(*) AS owner_count
            FROM   account_ownership
            WHERE  ownership_end_date IS NULL
            GROUP  BY account_id
        ),
        fiduciary_exists AS (
            SELECT account_id, TRUE AS has_fiduciary
            FROM   fiduciary_arrangement
        )
        SELECT
            a.account_id,
            a.account_number,
            arc.orc_code,
            arc.orc_verification_date,
            arc.is_joint_ownership,
            COALESCE(oc.owner_count, 0)    AS owner_count,
            arc.is_trust,
            COALESCE(fe.has_fiduciary, FALSE) AS has_fiduciary,
            CASE
                WHEN arc.orc_verification_date < :stale_cutoff
                                              THEN 'orc_verification_date > 365 days old'
                WHEN arc.is_joint_ownership = TRUE AND COALESCE(oc.owner_count, 0) < 2
                                              THEN 'is_joint_ownership=TRUE with <2 active owners'
                WHEN arc.is_trust = TRUE AND fe.has_fiduciary IS NULL
                                              THEN 'is_trust=TRUE but no fiduciary_arrangement'
            END AS failure_reason
        FROM account a
        JOIN account_regulatory_classification arc ON arc.account_id = a.account_id
        LEFT JOIN owner_counts   oc ON oc.account_id = a.account_id
        LEFT JOIN fiduciary_exists fe ON fe.account_id = a.account_id
        WHERE a.account_status IN ('Active', 'Dormant')
          AND (
              arc.orc_verification_date < :stale_cutoff
              OR (arc.is_joint_ownership = TRUE AND COALESCE(oc.owner_count, 0) < 2)
              OR (arc.is_trust = TRUE AND fe.has_fiduciary IS NULL)
          )
        ORDER BY a.account_number
        """,
        {"stale_cutoff": stale_cutoff},
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


async def control_a3_fiduciary_docs(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control A3 — Fiduciary Documentation Completeness & Freshness.

    Fails when:
      • document_file_reference IS NULL (no trust document on file).
      • document_verification_date is older than 730 days (biennial review required).

    Regulatory: FDIC Part 370 § 370.5 — Fiduciary accounts require documentation
    of the arrangement, including trust agreements and beneficiary information.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          fiduciary_id, account_id, fiduciary_type, document_file_reference,
          document_verification_date, failure_reason.
    """
    stale_cutoff = date.today() - timedelta(days=730)
    sql = text(
        """
        SELECT
            fa.fiduciary_id,
            fa.account_id,
            fa.fiduciary_type,
            fa.document_file_reference,
            fa.document_verification_date,
            CASE
                WHEN fa.document_file_reference IS NULL
                    THEN 'document_file_reference is NULL — no document on file'
                WHEN fa.document_verification_date < :stale_cutoff
                    THEN 'document_verification_date > 730 days old'
            END AS failure_reason
        FROM fiduciary_arrangement fa
        JOIN account a ON a.account_id = fa.account_id
        WHERE a.account_status IN ('Active', 'Dormant')
          AND (
              fa.document_file_reference IS NULL
              OR fa.document_verification_date < :stale_cutoff
          )
        ORDER BY fa.document_verification_date
        """,
        {"stale_cutoff": stale_cutoff},
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


async def control_a4_beneficiary_data(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control A4 — Fiduciary Beneficiary Distribution Integrity.

    Fails when:
      • SUM(distribution_percentage) is NOT BETWEEN 99.00 AND 101.00 for
        active beneficiaries (allowing ±1% rounding tolerance).
      • The oldest beneficiary_verification_date is more than 730 days ago.

    Regulatory: FDIC Part 330 § 330.10(d) — Named beneficiary coverage requires
    that each beneficiary is individually identified, verified, and their share
    documented.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          fiduciary_id, account_id, total_distribution_pct,
          oldest_verification_date, failure_reason.
    """
    stale_cutoff = date.today() - timedelta(days=730)
    sql = text(
        """
        SELECT
            fa.fiduciary_id,
            fa.account_id,
            SUM(fb.distribution_percentage)              AS total_distribution_pct,
            MIN(fb.beneficiary_verification_date)        AS oldest_verification_date,
            CASE
                WHEN SUM(fb.distribution_percentage) NOT BETWEEN 99 AND 101
                    THEN 'SUM(distribution_percentage) NOT BETWEEN 99 AND 101'
                WHEN MIN(fb.beneficiary_verification_date) < :stale_cutoff
                    THEN 'Oldest beneficiary_verification_date > 730 days'
            END AS failure_reason
        FROM fiduciary_arrangement fa
        JOIN fiduciary_beneficiary  fb ON fb.fiduciary_id  = fa.fiduciary_id
        JOIN account                a  ON a.account_id     = fa.account_id
        WHERE fb.beneficiary_status = 'Active'
          AND a.account_status IN ('Active', 'Dormant')
        GROUP BY fa.fiduciary_id, fa.account_id
        HAVING
            SUM(fb.distribution_percentage) NOT BETWEEN 99 AND 101
            OR MIN(fb.beneficiary_verification_date) < :stale_cutoff
        ORDER BY fa.fiduciary_id
        """,
        {"stale_cutoff": stale_cutoff},
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


async def control_a5_pod_tod(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control A5 — POD/TOD Designation Validity.

    Fails when:
      • beneficiary_form_on_file = FALSE (no signed form on file).
      • beneficiary_verification_date > 730 days old.
      • beneficiary_party_id IS NULL (beneficiary not linked to a party record).

    Regulatory: FDIC Part 370 § 370.5 — Payable-on-Death / Transfer-on-Death
    designations must be documented and kept current to qualify for separate
    $250K per-beneficiary coverage under FDIC Part 330 § 330.10.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          feature_id, account_id, beneficiary_party_id, beneficiary_form_on_file,
          beneficiary_verification_date, failure_reason.
    """
    stale_cutoff = date.today() - timedelta(days=730)
    sql = text(
        """
        SELECT
            af.feature_id,
            af.account_id,
            af.beneficiary_party_id,
            af.beneficiary_form_on_file,
            af.beneficiary_verification_date,
            CASE
                WHEN af.beneficiary_form_on_file = FALSE
                    THEN 'beneficiary_form_on_file = FALSE'
                WHEN af.beneficiary_verification_date < :stale_cutoff
                    THEN 'beneficiary_verification_date > 730 days old'
                WHEN af.beneficiary_party_id IS NULL
                    THEN 'beneficiary_party_id IS NULL — beneficiary not linked to party'
            END AS failure_reason
        FROM account_feature af
        JOIN account a ON a.account_id = af.account_id
        WHERE af.feature_type IN ('POD_PayableOnDeath', 'TOD_TransferOnDeath')
          AND af.feature_status = 'Active'
          AND a.account_status IN ('Active', 'Dormant')
          AND (
              af.beneficiary_form_on_file = FALSE
              OR af.beneficiary_verification_date < :stale_cutoff
              OR af.beneficiary_party_id IS NULL
          )
        ORDER BY af.account_id
        """,
        {"stale_cutoff": stale_cutoff},
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


async def control_a6_kyc_cip(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control A6 — KYC / CIP Verification Status.

    Fails when:
      • verification_status != 'Complete' for any party with active accounts.
      • verification_next_review_date < CURRENT_DATE (review is overdue).

    Regulatory: FinCEN CIP (31 U.S.C. § 5318) requires that all customers be
    identified and verified before account opening, with periodic re-review based
    on risk rating.  FDIC Part 370 § 370.4(a) requires current party information.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          verification_id, party_id, party_name, verification_status,
          risk_rating, verification_next_review_date, failure_reason.
    """
    today = date.today()
    sql = text(
        """
        SELECT
            k.verification_id,
            k.party_id,
            COALESCE(
                p.individual_name_given || ' ' || p.individual_name_family,
                p.organization_legal_name
            ) AS party_name,
            k.verification_status,
            k.risk_rating,
            k.verification_next_review_date,
            CASE
                WHEN k.verification_status != 'Complete'
                    THEN 'verification_status is ' || k.verification_status
                WHEN k.verification_next_review_date < :today
                    THEN 'verification_next_review_date is overdue (' || k.verification_next_review_date::text || ')'
            END AS failure_reason
        FROM kyc_cip_verification k
        JOIN party p ON p.party_id = k.party_id
        WHERE k.party_id IN (
            SELECT DISTINCT ao.owner_party_id
            FROM account_ownership ao
            JOIN account a ON a.account_id = ao.account_id
            WHERE a.account_status IN ('Active', 'Dormant')
              AND ao.ownership_end_date IS NULL
        )
          AND (
              k.verification_status != 'Complete'
              OR k.verification_next_review_date < :today
          )
        ORDER BY k.party_id
        """,
        {"today": today},
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


# ---------------------------------------------------------------------------
# B-Series: Balance / Transaction Controls
# ---------------------------------------------------------------------------

async def control_b1_daily_balance(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control B1 — Daily Balance Reconciliation.

    Fails when:
      • closing_balance != (opening + deposits - withdrawals + interest - fees
        + corrections) with tolerance ±$0.01.
      • gl_reconciliation_status != 'Reconciled'.
      • balance_as_of_date is older than 1 calendar day (stale snapshot).

    Regulatory: FDIC Part 370 § 360.8 — Each institution must maintain balance
    records current to the prior business day to enable timely insurance
    determination.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          account_id, balance_as_of_date, balance_closing_amount,
          computed_closing, variance, gl_reconciliation_status, failure_reason.
    """
    stale_cutoff = date.today() - timedelta(days=1)
    sql = text(
        """
        SELECT
            dab.account_id,
            a.account_number,
            dab.balance_as_of_date,
            dab.balance_closing_amount,
            (dab.balance_opening_amount
             + dab.balance_deposits_amount
             - dab.balance_withdrawals_amount
             + dab.balance_interest_amount
             - dab.balance_fees_amount
             + dab.balance_corrections_amount)             AS computed_closing,
            dab.balance_closing_amount -
            (dab.balance_opening_amount
             + dab.balance_deposits_amount
             - dab.balance_withdrawals_amount
             + dab.balance_interest_amount
             - dab.balance_fees_amount
             + dab.balance_corrections_amount)             AS variance,
            dab.gl_reconciliation_status,
            CASE
                WHEN ABS(
                    dab.balance_closing_amount -
                    (dab.balance_opening_amount
                     + dab.balance_deposits_amount
                     - dab.balance_withdrawals_amount
                     + dab.balance_interest_amount
                     - dab.balance_fees_amount
                     + dab.balance_corrections_amount)
                ) > 0.01
                    THEN 'Closing balance variance > $0.01'
                WHEN dab.gl_reconciliation_status != 'Reconciled'
                    THEN 'gl_reconciliation_status = ' || dab.gl_reconciliation_status
                WHEN dab.balance_as_of_date < :stale_cutoff
                    THEN 'balance_as_of_date older than 1 day'
            END AS failure_reason
        FROM daily_account_balance dab
        JOIN account a ON a.account_id = dab.account_id
        WHERE dab.balance_as_of_date = (
            SELECT MAX(d2.balance_as_of_date)
            FROM daily_account_balance d2
            WHERE d2.account_id = dab.account_id
        )
          AND (
              ABS(
                  dab.balance_closing_amount -
                  (dab.balance_opening_amount
                   + dab.balance_deposits_amount
                   - dab.balance_withdrawals_amount
                   + dab.balance_interest_amount
                   - dab.balance_fees_amount
                   + dab.balance_corrections_amount)
              ) > 0.01
              OR dab.gl_reconciliation_status != 'Reconciled'
              OR dab.balance_as_of_date < :stale_cutoff
          )
        ORDER BY dab.account_id
        """
    )
    result = await db.execute(sql, {"stale_cutoff": stale_cutoff})
    return [_row_to_dict(r) for r in result.fetchall()]


async def control_b3_interest_accrual(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control B3 — Interest Accrual Timeliness.

    Fails when:
      • interest_last_accrual_date is more than 30 days old for an
        interest-bearing account (interest_rate_percentage > 0).

    Regulatory: FDIC Part 370 § 370.4(b) — Accrued interest must be tracked and
    reflected in the balance for accurate insurance determination.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          account_id, account_number, interest_rate_percentage,
          interest_last_accrual_date, days_since_accrual, failure_reason.
    """
    stale_cutoff = date.today() - timedelta(days=30)
    sql = text(
        """
        SELECT
            a.account_id,
            a.account_number,
            a.account_type,
            a.interest_rate_percentage,
            a.interest_last_accrual_date,
            CURRENT_DATE - a.interest_last_accrual_date AS days_since_accrual,
            'interest_last_accrual_date > 30 days old' AS failure_reason
        FROM account a
        WHERE a.account_status IN ('Active', 'Dormant')
          AND a.interest_rate_percentage > 0
          AND (
              a.interest_last_accrual_date IS NULL
              OR a.interest_last_accrual_date < :stale_cutoff
          )
        ORDER BY a.interest_last_accrual_date NULLS FIRST
        """,
        {"stale_cutoff": stale_cutoff},
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


# ---------------------------------------------------------------------------
# C-Series: Coverage Calculation Controls
# ---------------------------------------------------------------------------

async def control_c2_coverage_calculation(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control C2 — Deposit Insurance Coverage Calculation Accuracy.

    Fails when:
      • calculation_test_result = 'Fail'.
      • |calculated_insured_amount + calculated_uninsured_amount
        - input_account_balance| > $0.01 (balance not fully allocated).
      • calculated_insured_amount > $250,000 for a Single-owner account.

    Regulatory: FDIC Part 330 § 330.1 et seq. — The SMDIA is $250,000 per
    depositor per institution per ownership category.  Part 370 § 370.3 requires
    the ability to calculate insurance within 24 hours of failure.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts with keys:
          calculation_id, account_id, orc_code, input_account_balance,
          calculated_insured_amount, calculated_uninsured_amount,
          allocation_variance, calculation_test_result, failure_reason.
    """
    sql = text(
        """
        SELECT
            dic.calculation_id,
            dic.account_id,
            a.account_number,
            dic.input_orc                             AS orc_code,
            dic.input_account_balance,
            dic.calculated_insured_amount,
            dic.calculated_uninsured_amount,
            ABS(
                dic.calculated_insured_amount
                + dic.calculated_uninsured_amount
                - dic.input_account_balance
            )                                         AS allocation_variance,
            dic.calculation_test_result,
            CASE
                WHEN dic.calculation_test_result = 'Fail'
                    THEN 'calculation_test_result = Fail'
                WHEN ABS(
                    dic.calculated_insured_amount
                    + dic.calculated_uninsured_amount
                    - dic.input_account_balance
                ) > 0.01
                    THEN 'insured + uninsured does not balance to input_account_balance (variance > $0.01)'
                WHEN dic.input_orc = 'Single'
                 AND dic.calculated_insured_amount > 250000
                    THEN 'Single-account calculated_insured_amount > $250,000'
            END AS failure_reason
        FROM deposit_insurance_calculation dic
        JOIN account a ON a.account_id = dic.account_id
        WHERE dic.calculation_date = (
            SELECT MAX(d2.calculation_date)
            FROM deposit_insurance_calculation d2
            WHERE d2.account_id = dic.account_id
        )
          AND (
              dic.calculation_test_result = 'Fail'
              OR ABS(
                  dic.calculated_insured_amount
                  + dic.calculated_uninsured_amount
                  - dic.input_account_balance
              ) > 0.01
              OR (dic.input_orc = 'Single' AND dic.calculated_insured_amount > 250000)
          )
        ORDER BY dic.account_id
        """
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


# ---------------------------------------------------------------------------
# G-Series: Management / Annual Certification
# ---------------------------------------------------------------------------

async def control_g1_annual_certification(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Control G1 — Annual Certification Summary (Part 370 § 370.3 Certification).

    Returns summary counts per calendar year:
      • total_accounts — total active accounts with a calculation for that year.
      • pass_count — calculations with test_result = 'Pass'.
      • fail_count — calculations with test_result = 'Fail'.
      • exception_count — calculations with test_result = 'Exception'.
      • total_insured — sum of calculated_insured_amount.
      • total_uninsured — sum of calculated_uninsured_amount.

    Regulatory: FDIC Part 370 § 370.3(c) — Each covered institution must conduct
    an annual test of its insurance determination system and certify results to
    the FDIC.  This query provides the annual summary data needed for that
    certification.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        List of dicts (one per calendar year), with keys:
          certification_year, total_accounts, pass_count, fail_count,
          exception_count, total_insured, total_uninsured.
    """
    sql = text(
        """
        SELECT
            EXTRACT(YEAR FROM dic.calculation_date)::INT       AS certification_year,
            COUNT(DISTINCT dic.account_id)                     AS total_accounts,
            COUNT(*) FILTER (WHERE dic.calculation_test_result = 'Pass')      AS pass_count,
            COUNT(*) FILTER (WHERE dic.calculation_test_result = 'Fail')      AS fail_count,
            COUNT(*) FILTER (WHERE dic.calculation_test_result = 'Exception') AS exception_count,
            SUM(dic.calculated_insured_amount)                 AS total_insured,
            SUM(dic.calculated_uninsured_amount)               AS total_uninsured
        FROM deposit_insurance_calculation dic
        GROUP BY EXTRACT(YEAR FROM dic.calculation_date)
        ORDER BY certification_year DESC
        """
    )
    result = await db.execute(sql)
    return [_row_to_dict(r) for r in result.fetchall()]


# ---------------------------------------------------------------------------
# Aggregated runner — all controls
# ---------------------------------------------------------------------------

CONTROL_REGISTRY: dict[str, Any] = {
    "a1": control_a1_orc_assignment,
    "a2": control_a2_orc_validation,
    "a3": control_a3_fiduciary_docs,
    "a4": control_a4_beneficiary_data,
    "a5": control_a5_pod_tod,
    "a6": control_a6_kyc_cip,
    "b1": control_b1_daily_balance,
    "b3": control_b3_interest_accrual,
    "c2": control_c2_coverage_calculation,
    "g1": control_g1_annual_certification,
}

CONTROL_DESCRIPTIONS: dict[str, str] = {
    "a1": "ORC Assignment Integrity (FDIC Part 370 § 370.3)",
    "a2": "ORC Validation Staleness & Consistency (FDIC Part 370 § 370.4)",
    "a3": "Fiduciary Documentation Completeness (FDIC Part 370 § 370.5)",
    "a4": "Beneficiary Distribution Integrity (FDIC Part 330 § 330.10(d))",
    "a5": "POD/TOD Designation Validity (FDIC Part 370 § 370.5)",
    "a6": "KYC/CIP Verification Status (FinCEN CIP 31 U.S.C. § 5318)",
    "b1": "Daily Balance Reconciliation (FDIC Part 370 § 360.8)",
    "b3": "Interest Accrual Timeliness (FDIC Part 370 § 370.4)",
    "c2": "Coverage Calculation Accuracy (FDIC Part 330 § 330.1)",
    "g1": "Annual Certification Summary (FDIC Part 370 § 370.3(c))",
}


async def run_all_controls(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """
    Execute all 10 audit controls and return a pass/fail summary.

    Per FDIC Part 370 § 370.3(c): the bank must be able to run a full
    end-to-end test of its insurance determination system.  This function
    provides that capability in a single call.

    Returns:
        Dict keyed by control_id (e.g. "a1") with values:
          {
            "control_id":    str,
            "description":   str,
            "status":        "PASS" | "FAIL",
            "failing_count": int,
            "failing_records": list[dict]  # empty if PASS
          }
    """
    summary: dict[str, dict[str, Any]] = {}
    for control_id, fn in CONTROL_REGISTRY.items():
        records = await fn(db)
        summary[control_id] = {
            "control_id":      control_id.upper(),
            "description":     CONTROL_DESCRIPTIONS[control_id],
            "status":          "FAIL" if records else "PASS",
            "failing_count":   len(records),
            "failing_records": records,
        }
    return summary
