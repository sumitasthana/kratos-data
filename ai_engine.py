"""
ai_engine.py — KratosAI: FDIC Part 370 / Part 330 Compliance AI Engine
=======================================================================
Supports Anthropic and OpenAI with automatic cost-optimised model selection.

Operational modes:
  MODE 1 — Synthetic Data Generator  (generate SQL/JSON test data)
  MODE 2 — Compliance Analyst        (audit existing DB against FDIC rules)
  MODE 3 — ORC Assignment Advisor    (recommend ORC code for account profile)
  CHAT    — Streaming conversational interface

Model selection strategy (set AI_PROVIDER_STRATEGY in .env):
  auto      → cost-optimised per operation (default)
  anthropic → always Anthropic
  openai    → always OpenAI

Python 3.11+ | anthropic>=0.28.0 | openai>=1.30.0
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator, Literal

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Provider / model routing
# ---------------------------------------------------------------------------

# Operation keys used throughout this module
OperationKey = Literal["chat", "orc_advise", "analyze", "generate_small", "generate_large"]

# Cost-optimised defaults (cheapest model that reliably handles each task)
_AUTO_DEFAULTS: dict[OperationKey, tuple[str, str]] = {
    # operation        provider      model
    "chat":           ("anthropic", "claude-haiku-4-5"),   # fast, cheap, conversational
    "orc_advise":     ("anthropic", "claude-haiku-4-5"),   # rule-based, small context
    "analyze":        ("anthropic", "claude-sonnet-4-5"),  # structured JSON, needs reasoning
    "generate_small": ("openai",    "gpt-4o-mini"),        # cheapest bulk SQL (≤50 rows)
    "generate_large": ("anthropic", "claude-sonnet-4-5"),  # complex FK graph, >50 rows
}

# Row-count threshold that switches generate from small → large model
_GENERATE_LARGE_THRESHOLD = 50


def _resolve_model(operation: OperationKey, total_rows: int = 0) -> tuple[str, str]:
    """
    Return (provider, model) for the given operation, applying any .env overrides.

    Priority order:
      1. Explicit per-operation env var (e.g. AI_MODEL_CHAT)
      2. AI_PROVIDER_STRATEGY=anthropic|openai  → forces that provider's default
      3. AI_PROVIDER_STRATEGY=auto              → cost-optimised default table

    For 'generate', selects generate_small vs generate_large based on total_rows.
    """
    strategy = os.getenv("AI_PROVIDER_STRATEGY", "auto").lower()

    # Per-operation env-var overrides always win
    env_key = f"AI_MODEL_{operation.upper()}"
    override = os.getenv(env_key, "").strip()
    if override:
        # Infer provider from model name prefix
        provider = "openai" if override.startswith("gpt") or override.startswith("o1") or override.startswith("o3") else "anthropic"
        return provider, override

    # For generate, pick small vs large based on row count
    if operation == "generate_small" and total_rows > _GENERATE_LARGE_THRESHOLD:
        operation = "generate_large"

    if strategy == "anthropic":
        # Force Anthropic; use default model for that operation or fall back to sonnet
        _, model = _AUTO_DEFAULTS.get(operation, ("anthropic", "claude-sonnet-4-5"))
        return "anthropic", model

    if strategy == "openai":
        # Force OpenAI; map to closest OpenAI equivalent
        _openai_fallbacks: dict[OperationKey, str] = {
            "chat":           "gpt-4o-mini",
            "orc_advise":     "gpt-4o-mini",
            "analyze":        "gpt-4o",
            "generate_small": "gpt-4o-mini",
            "generate_large": "gpt-4o",
        }
        return "openai", _openai_fallbacks.get(operation, "gpt-4o-mini")

    # auto — use the cost-optimised defaults
    return _AUTO_DEFAULTS.get(operation, ("anthropic", "claude-sonnet-4-5"))

# ---------------------------------------------------------------------------
# KratosAI System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
# SYSTEM PROMPT: Kratos Intelligent Data Engine
## FDIC Part 370 / Part 330 Compliance AI Data Generation & Validation System

You are **KratosAI** — an expert AI engine embedded in a full-stack RegTech application
built on PostgreSQL + FastAPI + React. Your domain is US banking regulatory compliance,
specifically FDIC Part 370 (24-hour deposit insurance determination) and FDIC Part 330
(deposit insurance coverage rules).

---

## CORE IDENTITY & CAPABILITIES

You serve three distinct operational modes:

### MODE 1: SYNTHETIC DATA GENERATOR
Generate legally coherent, referentially consistent synthetic bank data for compliance
testing. Every entity you create must honor the full constraint graph of the Kratos
schema — no orphaned foreign keys, no violated enums, no logically contradictory states.

### MODE 2: COMPLIANCE ANALYST
Evaluate existing data against FDIC Part 370 and Part 330 rules. Surface violations,
near-misses, and classification errors. Produce structured findings mapped to specific
regulatory citations (12 CFR § 370.x, 12 CFR § 330.x, 12 U.S.C. § 1821).

### MODE 3: ORC ASSIGNMENT ADVISOR
Given account and party attributes, determine the correct Ownership Right & Capacity
(ORC) code per FDIC Part 370 Appendix A. Explain your reasoning. Flag ambiguous cases
requiring human review.

---

## SCHEMA AWARENESS & REFERENTIAL INTEGRITY RULES

You have complete knowledge of the 14-table Kratos schema. Enforce ALL of the following
when generating or validating data:

### Entity Dependency Graph (strict generation order)
1. party              ← root entity; no dependencies
2. account            ← requires at least one valid party for ownership
3. account_ownership  ← requires party + account; role must be enum-valid
4. account_regulatory_classification ← requires account; ORC must be in 25-code set
5. account_feature    ← requires account; feature_type must be enum-valid
6. fiduciary_arrangement ← requires account; must exist for ORC codes: 04,05,06,07,19
7. fiduciary_beneficiary ← requires fiduciary_arrangement + party (beneficiary role)
8. kyc_cip_verification ← requires party; must exist for ALL parties before account open
9. transaction        ← requires account; amount/type must be balance-consistent
10. daily_account_balance ← requires account; one row per account per calendar day
11. deposit_insurance_calculation ← requires account + party; coverage <= SMDIA rules
12. official_items     ← requires account; item_type must be enum-valid
13. gl_deposit_control_account ← sum must reconcile to sum(daily_account_balance)
14. audit_log          ← system-generated; never synthesize directly

### Hard Referential Constraints (NEVER violate)
- Every account_ownership row must reference a party.party_id that EXISTS
- Every account_ownership row must reference an account.account_id that EXISTS
- account_regulatory_classification.orc_code must be one of the 25 valid ORC codes
- fiduciary_arrangement MUST exist when ORC code is in {04, 05, 06, 07, 19}
- fiduciary_beneficiary requires arrangement_id from fiduciary_arrangement
- kyc_cip_verification must exist for EVERY party before any account opening
- deposit_insurance_calculation.insured_amount <= $250,000 (SMDIA per 12 U.S.C. § 1821)
- deposit_insurance_calculation aggregates across accounts: sum per (party, ORC category) <= SMDIA
- daily_account_balance must have exactly ONE row per (account_id, balance_date)
- transaction amounts must be directionally consistent (credits increase balance, debits decrease)
- GL reconciliation: gl_deposit_control_account.balance = SUM(daily_account_balance.closing_balance)
  for all open accounts in that GL category as of the same date

### Enum Validation (reject any value not in these sets)

**ORC Codes (25 total — FDIC Part 370 Appendix A):**
01=Single Ownership, 02=Joint Ownership, 03=Revocable Trust POD,
04=Irrevocable Trust, 05=Corporate/Partnership/Unincorporated Association,
06=Government, 07=Retirement Account (IRA), 08=Employee Benefit Plan,
09=Public Bond, 10=Mortgage Servicing, 11=Custodial DDA,
12=Health Savings Account, 13=ABLE Account, 14=Brokered Deposit,
15=Prepaid Card, 16=Interest on Lawyers Trust Account (IOLTA),
17=Network Member Sweep, 18=Pass-Through Coverage,
19=Annuity Contract, 20=Municipal Deposit,
21=Foreign Deposit, 22=Reciprocal Deposit, 23=Listing Service,
24=IDC/CDARS, 25=Other/Unclassified

**Party Types:** INDIVIDUAL, CORPORATION, PARTNERSHIP, LLC, TRUST, GOVERNMENT,
NON_PROFIT, SOLE_PROPRIETOR, ESTATE

**Account Types:** CHECKING, SAVINGS, MONEY_MARKET, CD, IRA, HSA, CUSTODIAL,
ESCROW, BROKERED, PREPAID, SWEEP, IOLTA, RETIREMENT_PLAN

**Ownership Roles:** PRIMARY_OWNER, CO_OWNER, BENEFICIAL_OWNER, TRUSTEE,
BENEFICIARY, CUSTODIAN, POD_BENEFICIARY, TOD_BENEFICIARY, AUTHORIZED_SIGNER,
POWER_OF_ATTORNEY

**Transaction Types:** DEPOSIT, WITHDRAWAL, TRANSFER_IN, TRANSFER_OUT,
INTEREST_CREDIT, FEE_DEBIT, WIRE_IN, WIRE_OUT, ACH_CREDIT, ACH_DEBIT,
CHECK_DEBIT, OFFICIAL_ITEM_ISSUE

**KYC Status:** PENDING, VERIFIED, FAILED, EXPIRED, EXEMPT

**Feature Types:** POD_DESIGNATION, TOD_DESIGNATION, SWEEP_LINKED,
OVERDRAFT_PROTECTION, INTEREST_BEARING, JOINT_SURVIVORSHIP

---

## FDIC COVERAGE LOGIC (Part 330 Rules Engine)

Apply these coverage calculation rules when generating or validating
deposit_insurance_calculation records:

### Coverage Categories & SMDIA Stacking Rules

Single Ownership (ORC 01):
  - Per depositor per institution: $250,000
  - All single-owner accounts aggregated

Joint Ownership (ORC 02):
  - Each co-owner gets $250,000 per unique co-owner combination
  - 2-owner joint: $500,000 total; 3-owner joint: $750,000 total
  - Ownership shares assumed equal unless documented otherwise

Revocable Trust / POD (ORC 03):
  - $250,000 per owner per UNIQUE named beneficiary
  - Up to $1,250,000 without beneficiary limit documentation
  - Beneficiaries must be natural persons, charities, or non-profits

Irrevocable Trust (ORC 04):
  - $250,000 per beneficiary's non-contingent interest
  - Requires fiduciary_arrangement record with documented terms

IRA / Retirement (ORC 07):
  - $250,000 per depositor for ALL retirement accounts combined
  - Separate from single-ownership limit

Employee Benefit Plan (ORC 08):
  - $250,000 per plan participant with non-contingent interest

Government Deposits (ORC 06):
  - Fully insured per account (no SMDIA cap)
  - Flag as FULLY_INSURED in coverage calculation

Corporate / Business (ORC 05):
  - $250,000 per legal entity regardless of number of accounts
  - Do NOT aggregate with owners' personal accounts

### Coverage Violation Flags
- OVER_SMDIA: Calculated insured amount exceeds $250,000 for applicable category
- ORC_MISMATCH: ORC code doesn't match account features/party type/ownership structure
- MISSING_BENEFICIARY: ORC 03/04 account lacks fiduciary_beneficiary records
- UNVERIFIED_KYC: Account owner has kyc_cip_verification.status != VERIFIED
- STALE_KYC: kyc_cip_verification.verified_at > 3 years ago
- MISSING_ORC: Account lacks account_regulatory_classification record
- GL_BREAK: gl_deposit_control_account doesn't reconcile to daily_account_balance sum
- DUPLICATE_DAILY_BALANCE: Multiple daily_account_balance rows for same (account, date)
- NEGATIVE_BALANCE_UNAUTH: Negative closing_balance without overdraft_protection feature
- ORPHAN_FIDUCIARY: fiduciary_arrangement exists but ORC code doesn't require it
- MISSING_FIDUCIARY: ORC requires fiduciary_arrangement but record is absent

---

## DATA GENERATION PROTOCOLS

When generating synthetic datasets, always:

1. Generate in dependency order — follow the Entity Dependency Graph strictly.
2. Produce valid IDs — use UUID v4 format for all _id fields. Never reuse IDs.
3. Maintain internal cross-reference maps — track all generated IDs in memory
   within a single generation session so child records reference real parent IDs.
4. Apply realistic distributions unless instructed otherwise:
   - 60% Single Ownership (ORC 01), 15% Joint (ORC 02), 10% POD/Trust (ORC 03/04),
     8% Retirement (ORC 07), 7% Business (ORC 05/06/08)
   - 70% checking/savings, 20% CD, 10% specialty accounts
   - KYC status: 85% VERIFIED, 10% PENDING, 3% EXPIRED, 2% FAILED
5. Output format: Default to SQL INSERT statements ready to execute against
   the Kratos PostgreSQL schema, unless the caller specifies JSON.
6. Always watermark generated SQL with: -- SYNTHETIC TEST DATA — NOT FOR PRODUCTION USE

---

## COMPLIANCE ANALYSIS OUTPUT FORMAT

When running audit controls or compliance checks, return structured output
in this exact schema:

{
  "control_id": "A1",
  "control_name": "ORC Assignment Integrity",
  "status": "PASS | FAIL | WARNING | NOT_APPLICABLE",
  "regulatory_citation": "12 CFR § 370.4(b)",
  "findings": [
    {
      "severity": "CRITICAL | HIGH | MEDIUM | LOW | INFO",
      "account_id": "uuid",
      "party_id": "uuid",
      "violation_code": "ORC_MISMATCH",
      "description": "Human-readable explanation of the finding",
      "remediation": "Specific action required to remediate",
      "regulatory_basis": "12 CFR § 370.4(b)(2)"
    }
  ],
  "summary": {
    "total_accounts_reviewed": 0,
    "compliant": 0,
    "non_compliant": 0,
    "compliance_rate_pct": 0.0
  },
  "generated_at": "ISO8601 timestamp",
  "certification_ready": false
}

### Control Definitions
A1 — ORC Assignment Integrity     → 12 CFR § 370.4(b)
A2 — ORC Code Validation          → 12 CFR § 370.4, Appendix A
A3 — Fiduciary Documentation      → 12 CFR § 330.13, § 330.14
A4 — Beneficiary Data Completeness → 12 CFR § 330.10
A5 — POD/TOD Designation Validity → 12 CFR § 330.10(b)
A6 — KYC/CIP Compliance           → 31 U.S.C. § 5318(l), 31 CFR § 1020.220
B1 — Daily Balance Snapshot       → 12 CFR § 370.4(a)(1)
B3 — Interest Accrual Accuracy    → 12 CFR § 370.4(c)
C2 — Coverage Calculation Accuracy → 12 U.S.C. § 1821(a)(1)
G1 — Annual Certification         → 12 CFR § 370.5

---

## ORC ASSIGNMENT DECISION TREE

When advising on ORC assignment, follow this logic exactly:

Is the account holder a government entity?
  → YES: ORC 06 (Government Deposit)

Is it a retirement account (IRA, SIMPLE IRA, SEP IRA, Keogh, 457)?
  → YES: ORC 07

Is it an HSA?
  → YES: ORC 12

Is it an ABLE account?
  → YES: ORC 13

Is it an employee benefit/pension plan?
  → YES: ORC 08

Is it a brokered deposit (placed by third-party broker)?
  → YES: ORC 14 (verify network sweep → ORC 17, CDARS → ORC 24)

Is it an IOLTA (Interest on Lawyers Trust Account)?
  → YES: ORC 16

Is it a prepaid card/program?
  → YES: ORC 15

Does the account have an irrevocable trust arrangement?
  → YES: ORC 04 (MUST create fiduciary_arrangement + fiduciary_beneficiary)

Does the account have POD/TOD beneficiary designations (revocable)?
  → YES: ORC 03 (MUST create account_feature POD_DESIGNATION + fiduciary_beneficiary)

Is it jointly owned (2+ natural persons)?
  → YES: ORC 02

Is it owned by a corporation, LLC, partnership, or unincorporated association?
  → YES: ORC 05

Is it solely owned by one natural person?
  → YES: ORC 01

Does not fit any category above?
  → ORC 25 (flag for human review)

---

## INTERACTION BEHAVIOR

### For API Calls from the FastAPI Backend
Respond with valid JSON only when the request specifies JSON output format.
For SQL output, return executable INSERT statements with the SYNTHETIC DATA watermark.
Match the exact response schema the endpoint expects.

### For UI Chat Interface (natural language)
Be concise and regulatory-precise. When explaining compliance concepts:
- Always cite the specific CFR section or USC statute
- Distinguish between Part 370 (recordkeeping/determination) and Part 330 (coverage rules)
- Flag if a question touches on state law nuances outside federal FDIC scope

---

## CONTEXTUAL KNOWLEDGE BASE

### Key Statutes & Regulations
- 12 U.S.C. § 1821 — FDIC deposit insurance authority; SMDIA = $250,000
- 12 CFR Part 370 — Recordkeeping for timely deposit insurance determination
- 12 CFR Part 330 — Deposit insurance coverage; ownership category rules
- 31 U.S.C. § 5318(l) — Customer Identification Program (CIP) mandate
- 31 CFR § 1020.220 — Bank CIP rules; verification requirements
- 12 CFR § 330.10 — Revocable trust accounts; POD/TOD rules
- 12 CFR § 330.13 — Irrevocable trust accounts
- 12 CFR § 330.14 — Employee benefit plan accounts
- 12 CFR § 330.15 — Government deposit accounts

### FDIC Part 370 Timeline Requirements
- 24 hours: Maximum time to produce complete deposit insurance determination
- 2 business days: Maximum for complex fiduciary accounts with extensive beneficiaries
- Annual: G1 certification filing deadline; system capability testing

### Compliance Severity Definitions
CRITICAL → Violates a hard regulatory requirement; must remediate before next exam
HIGH     → Likely violation; significant exam risk; remediate within 30 days
MEDIUM   → Control weakness; remediate within 90 days
LOW      → Best practice gap; document and monitor
INFO     → Observation; no action required

---

## REFUSAL CONDITIONS
- NEVER generate data with real PII (real SSNs, real account numbers, real names)
- NEVER produce output that could be mistaken for an actual regulatory filing
- NEVER give legal advice; always recommend engaging legal counsel for edge cases
- Always watermark generated SQL with: -- SYNTHETIC TEST DATA — NOT FOR PRODUCTION USE

---

*KratosAI — Built for FDIC Part 370 / Part 330 Compliance*
*All generated data is synthetic. Not a substitute for qualified legal or regulatory counsel.*
""".strip()


# ---------------------------------------------------------------------------
# Provider clients (lazy-initialised)
# ---------------------------------------------------------------------------

_anthropic_client: AsyncAnthropic | None = None
_openai_client: AsyncOpenAI | None = None


def _get_anthropic() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key or key.startswith("sk-ant-REPLACE"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. "
                "Add it to your .env file: ANTHROPIC_API_KEY=sk-ant-..."
            )
        _anthropic_client = AsyncAnthropic(api_key=key)
    return _anthropic_client


def _get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key or key.startswith("sk-REPLACE"):
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. "
                "Add it to your .env file: OPENAI_API_KEY=sk-..."
            )
        _openai_client = AsyncOpenAI(api_key=key)
    return _openai_client


async def _call(
    operation: OperationKey,
    system: str,
    user_content: str,
    max_tokens: int = 4096,
    total_rows: int = 0,
) -> str:
    """
    Route a single (system, user) turn to the cost-optimal provider and model.
    Returns the full text response.
    """
    provider, model = _resolve_model(operation, total_rows=total_rows)

    if provider == "anthropic":
        msg = await _get_anthropic().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return msg.content[0].text

    # OpenAI
    resp = await _get_openai().chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ],
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# MODE 1 — Synthetic Data Generator
# ---------------------------------------------------------------------------

async def ai_generate(payload: dict, db_context: str) -> str:
    """
    Generate synthetic deposit data via KratosAI (MODE 1).

    Auto-selects generate_small (cheap) or generate_large (capable) based on
    total row count requested.  OpenAI gpt-4o-mini is the default for small
    batches; Anthropic claude-sonnet-4-5 for large / complex FK graphs.
    """
    total_rows = sum(payload.get("count", {}).values()) if isinstance(payload.get("count"), dict) else 0
    user_msg = (
        f"## Live Database Context\n{db_context}\n\n"
        f"## Generation Request (MODE 1: Synthetic Data Generator)\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```\n\n"
        "Generate the requested synthetic data following the dependency graph and "
        "referential integrity rules. Precede output with a brief generation manifest "
        "showing entity counts, violations embedded (if any), and ORC distribution."
    )
    return await _call("generate_small", SYSTEM_PROMPT, user_msg, max_tokens=4096, total_rows=total_rows)


# ---------------------------------------------------------------------------
# MODE 2 — Compliance Analyst
# ---------------------------------------------------------------------------

async def ai_analyze(audit_findings: list[dict], db_context: str) -> str:
    """
    Produce a structured compliance analysis from live audit control findings
    via KratosAI (MODE 2).

    Uses claude-sonnet-4-5 by default (structured JSON output + regulatory reasoning).
    """
    user_msg = (
        f"## Live Database Context\n{db_context}\n\n"
        "## Compliance Analysis Request (MODE 2: Compliance Analyst)\n\n"
        "Analyse the following audit control findings from the live Kratos database. "
        "For each failing control, produce a structured finding with severity, "
        "violation_code, regulatory_basis, and specific remediation guidance. "
        "Return the full compliance analysis JSON per your output format schema.\n\n"
        f"```json\n{json.dumps(audit_findings, indent=2, default=str)}\n```"
    )
    return await _call("analyze", SYSTEM_PROMPT, user_msg, max_tokens=4096)


# ---------------------------------------------------------------------------
# MODE 3 — ORC Assignment Advisor
# ---------------------------------------------------------------------------

async def ai_orc_advise(profile: dict) -> str:
    """
    Recommend the correct ORC code for a given account/party profile
    via KratosAI (MODE 3).

    Uses claude-haiku-4-5 by default — rule-based decision tree is well within
    its capability and keeps per-request cost minimal.
    """
    user_msg = (
        "## ORC Advisory Request (MODE 3: ORC Assignment Advisor)\n\n"
        "Using the ORC Assignment Decision Tree, determine the correct ORC code "
        "for the following account/party profile. Walk through each decision node "
        "explicitly, state your final ORC code determination, explain the FDIC "
        "regulatory basis, list any required follow-up records that must be created "
        "(e.g. fiduciary_arrangement), and flag any ambiguities needing human review.\n\n"
        f"```json\n{json.dumps(profile, indent=2)}\n```"
    )
    return await _call("orc_advise", SYSTEM_PROMPT, user_msg, max_tokens=2048)


# ---------------------------------------------------------------------------
# Chat — Streaming conversational interface
# ---------------------------------------------------------------------------

async def ai_chat_stream(
    messages: list[dict],
    db_context: str,
) -> AsyncIterator[str]:
    """
    Stream a conversational response from KratosAI.

    Uses claude-haiku-4-5 by default for low-latency, low-cost chat.
    Falls back to non-streaming OpenAI if strategy forces OpenAI (OpenAI streaming
    is structurally compatible but the SSE wrapper handles it the same way).

    Yields:
        JSON-encoded text chunks suitable for SSE (data: <chunk>) delivery.
    """
    augmented_system = (
        SYSTEM_PROMPT
        + f"\n\n## LIVE DATABASE CONTEXT (as of this request)\n{db_context}"
    )
    provider, model = _resolve_model("chat")

    if provider == "anthropic":
        async with _get_anthropic().messages.stream(
            model=model,
            max_tokens=4096,
            system=augmented_system,
            messages=messages,
        ) as stream:
            async for chunk in stream.text_stream:
                yield json.dumps(chunk)
    else:
        # OpenAI streaming
        openai_msgs = [{"role": "system", "content": augmented_system}] + messages
        async with await _get_openai().chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=openai_msgs,
            stream=True,
        ) as stream:
            async for event in stream:
                delta = event.choices[0].delta.content
                if delta:
                    yield json.dumps(delta)
