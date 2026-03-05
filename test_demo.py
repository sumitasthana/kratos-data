"""
test_demo.py — Kratos Data: FDIC Part 370 / Part 330 Demo Test Suite
=====================================================================
Pytest test suite covering core FDIC compliance scenarios:
  - Party and account creation
  - ORC assignment and coverage calculation
  - Joint, trust, and IRA-specific coverage rules
  - Audit control detection of defects
  - Trigger-based audit log firing

Pre-requisites:
  pip install pytest pytest-asyncio asyncpg sqlalchemy[asyncio] pydantic fastapi httpx

Environment variables:
  DATABASE_URL_TEST  — async PostgreSQL DSN for test DB (read from .env via python-dotenv)
  TEST_DATABASE_URL  — legacy alias; DATABASE_URL_TEST takes precedence

The test DB must have the DDL applied (01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql)
and the audit trigger installed (04_AUDIT_TRIGGER.sql).

Each test function runs inside a savepoint; the outer transaction is rolled
back after every test to keep the DB clean.

Python 3.11+ | pytest-asyncio 0.23+ | SQLAlchemy 2.x async
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
import uuid

load_dotenv()  # reads .env from the project root; no-op if already loaded
from datetime import date, timedelta
from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from orc_engine import (
    AccountORM,
    AccountOwnershipORM,
    AccountRegulatoryClassificationORM,
    DepositInsuranceCalculationORM,
    PartyORM,
    assign_orc_code,
    calculate_fdic_coverage,
    upsert_insurance_calculation,
    AccountStatusEnum,
    AccountTypeEnum,
    InsuranceCategoryEnum,
    OrcCodeEnum,
    OrcDeterminationMethodEnum,
    OwnershipRoleEnum,
    PartyStatusEnum,
    PartyTypeEnum,
    VerificationMethodEnum,
    CalculationScenarioEnum,
    SMDIA,
)
from audit_controls import (
    control_a1_orc_assignment,
    control_b1_daily_balance,
    control_c2_coverage_calculation,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Reads DATABASE_URL_TEST from .env; falls back to TEST_DATABASE_URL for backward compatibility.
TEST_DATABASE_URL: str = (
    os.getenv("DATABASE_URL_TEST")
    or os.getenv("TEST_DATABASE_URL")
    or "postgresql+asyncpg://postgres:CHANGE_ME_ENCODED@localhost:5432/atomic_deposit_system_test"
)

# ---------------------------------------------------------------------------
# Session-scoped engine; function-scoped session with nested transaction
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create the async engine once per test session."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture()
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session that wraps each test in a savepoint so the
    outer transaction can be rolled back, leaving the DB clean after each test.
    """
    async with engine.begin() as outer_conn:
        # Begin an outer non-autocommit transaction
        session_factory = async_sessionmaker(
            bind=outer_conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with session_factory() as session:
            yield session
            # Roll back the savepoint — DB state is restored
            await session.rollback()


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

async def make_party(
    db: AsyncSession,
    given: str = "Test",
    family: str = "User",
    ssn: str = "999888777",
) -> PartyORM:
    """Insert a minimal individual party and return the ORM object."""
    party = PartyORM(
        party_type             = PartyTypeEnum.Individual,
        party_status           = PartyStatusEnum.Active,
        individual_name_given  = given,
        individual_name_family = family,
        individual_ssn         = ssn,
        individual_date_of_birth = date(1985, 1, 1),
        address_city           = "New York",
        address_state_province = "NY",
        address_country        = "US",
        address_is_usa         = True,
        created_by             = "test_runner",
        modified_by            = "test_runner",
    )
    db.add(party)
    await db.flush()
    return party


async def make_account(
    db: AsyncSession,
    owner_party_id: uuid.UUID,
    account_type: str = "Savings",
    balance: Decimal = Decimal("10000.00"),
    account_number: str | None = None,
) -> AccountORM:
    """Insert a minimal account and return the ORM object."""
    acct = AccountORM(
        account_number               = account_number or f"TEST-{uuid.uuid4().hex[:8].upper()}",
        account_type                 = AccountTypeEnum(account_type),
        account_status               = AccountStatusEnum.Active,
        account_open_date            = date.today(),
        primary_owner_party_id       = owner_party_id,
        interest_rate_percentage     = Decimal("2.0000"),
        interest_rate_effective_date = date.today(),
        current_balance              = balance,
        current_balance_date         = date.today(),
        accrued_interest_not_posted  = Decimal("0.00"),
        minimum_balance              = Decimal("0.00"),
        interest_last_accrual_date   = date.today(),
        created_by                   = "test_runner",
        modified_by                  = "test_runner",
    )
    db.add(acct)
    await db.flush()
    return acct


async def make_ownership(
    db: AsyncSession,
    account_id: uuid.UUID,
    party_id: uuid.UUID,
    role: str = "PrimaryOwner",
    pct: Decimal = Decimal("100.00"),
) -> AccountOwnershipORM:
    """Insert an account_ownership row."""
    row = AccountOwnershipORM(
        account_id                    = account_id,
        owner_party_id                = party_id,
        ownership_role                = OwnershipRoleEnum(role),
        ownership_percentage_amount   = pct,
        ownership_effective_date      = date.today(),
        ownership_verification_date   = date.today(),
        ownership_verification_method = VerificationMethodEnum.DocumentReview,
        created_by                    = "test_runner",
    )
    db.add(row)
    await db.flush()
    return row


async def make_classification(
    db: AsyncSession,
    account_id: uuid.UUID,
    orc_code: str = "Single",
    is_joint: bool = False,
    is_ira: bool = False,
    is_trust: bool = False,
) -> AccountRegulatoryClassificationORM:
    """Insert an account_regulatory_classification row."""
    cls = AccountRegulatoryClassificationORM(
        account_id                   = account_id,
        orc_code                     = OrcCodeEnum(orc_code),
        orc_insured_amount_per_owner = SMDIA,
        orc_insurance_category       = InsuranceCategoryEnum.Covered,
        orc_determination_date       = date.today(),
        orc_determination_method     = OrcDeterminationMethodEnum.RegistrationForm,
        orc_verification_date        = date.today(),
        is_joint_ownership           = is_joint,
        is_ira                       = is_ira,
        is_trust                     = is_trust,
        created_by                   = "test_runner",
    )
    db.add(cls)
    await db.flush()
    return cls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_individual_party(db: AsyncSession) -> None:
    """
    Verify that an individual party can be inserted with all required fields.
    Per FinCEN CIP (31 U.S.C. § 5318): each customer must have a valid
    identity record before account opening.
    """
    party = await make_party(db, given="Alice", family="Walker", ssn="111000999")

    assert party.party_id is not None
    assert party.party_type == "Individual"
    assert party.party_status == "Active"
    assert party.individual_name_given == "Alice"
    assert party.individual_name_family == "Walker"
    assert party.individual_ssn == "111000999"


@pytest.mark.asyncio
async def test_create_savings_account_with_orc(db: AsyncSession) -> None:
    """
    Verify that a savings account (single owner) receives ORC = 'Single' and
    an FDIC coverage calculation row is inserted correctly.
    Per FDIC Part 370 § 370.3(b): ORC must be assigned at account opening.
    """
    party = await make_party(db, ssn="222000111")
    acct  = await make_account(db, party.party_id, "Savings", Decimal("50000.00"))
    await make_ownership(db, acct.account_id, party.party_id, "PrimaryOwner", Decimal("100.00"))

    orc = assign_orc_code("Savings", owner_count=1, has_beneficiaries=False)
    assert orc == OrcCodeEnum.Single

    cls = await make_classification(db, acct.account_id, orc_code=orc.value)
    calc = await upsert_insurance_calculation(
        account_id = acct.account_id,
        db_session = db,
        scenario   = CalculationScenarioEnum.Normal,
        created_by = "test_runner",
    )

    assert calc.input_orc == "Single"
    assert calc.calculated_insured_amount  == Decimal("50000.00")
    assert calc.calculated_uninsured_amount == Decimal("0.00")
    assert calc.calculation_test_result.value == "Pass"


@pytest.mark.asyncio
async def test_joint_account_coverage_calculation(db: AsyncSession) -> None:
    """
    Verify that a Joint JTWROS account with 2 owners receives coverage
    capped at min(balance, $250,000 × 2) = min(balance, $500,000).

    Per FDIC Part 330 § 330.9: each co-owner of a joint account is separately
    insured up to $250,000 for their interests in all joint accounts at the
    same institution.
    """
    # Two owners, balance $350,000 — fully covered ($350K < $500K cap)
    result = calculate_fdic_coverage(
        orc_code          = "Joint_JTWROS",
        balance           = Decimal("350000.00"),
        owner_count       = 2,
        beneficiary_count = 0,
    )
    assert result["insured"]   == 350000.0
    assert result["uninsured"] == 0.0
    assert "Joint_JTWROS" in result["orc"]

    # Two owners, balance $600,000 — partially covered (cap = $500K)
    result2 = calculate_fdic_coverage(
        orc_code          = "Joint_JTWROS",
        balance           = Decimal("600000.00"),
        owner_count       = 2,
        beneficiary_count = 0,
    )
    assert result2["insured"]   == pytest.approx(500000.0)
    assert result2["uninsured"] == pytest.approx(100000.0)


@pytest.mark.asyncio
async def test_trust_account_coverage_3_beneficiaries(db: AsyncSession) -> None:
    """
    Verify that a Trust Revocable account with 3 named beneficiaries receives
    coverage capped at min(balance, $250,000 × 3) = min(balance, $750,000).

    Per FDIC Part 330 § 330.10(d): each named beneficiary of a revocable trust
    is separately insured up to $250,000, with a maximum of 5 beneficiaries
    ($1,250,000 cap).
    """
    # Balance = $400,000, 3 beneficiaries → cap = $750,000 → all insured
    result = calculate_fdic_coverage(
        orc_code          = "Trust_Revocable",
        balance           = Decimal("400000.00"),
        owner_count       = 1,
        beneficiary_count = 3,
    )
    assert result["insured"]   == pytest.approx(400000.0)
    assert result["uninsured"] == pytest.approx(0.0)

    # Balance = $900,000, 3 beneficiaries → cap = $750,000 → $150K uninsured
    result2 = calculate_fdic_coverage(
        orc_code          = "Trust_Revocable",
        balance           = Decimal("900000.00"),
        owner_count       = 1,
        beneficiary_count = 3,
    )
    assert result2["insured"]   == pytest.approx(750000.0)
    assert result2["uninsured"] == pytest.approx(150000.0)


@pytest.mark.asyncio
async def test_ira_account_separate_coverage(db: AsyncSession) -> None:
    """
    Verify that an IRA Traditional account receives separate $250,000 coverage
    independent of the depositor's single-ownership accounts.

    Per FDIC Part 330 § 330.14: certain retirement accounts (IRAs, Keogh plans)
    are separately insured for up to $250,000 per depositor per institution.
    """
    # IRA balance above SMDIA → capped at $250,000
    result_high = calculate_fdic_coverage(
        orc_code          = "IRA_Traditional",
        balance           = Decimal("320000.00"),
        owner_count       = 1,
        beneficiary_count = 0,
    )
    assert result_high["insured"]   == pytest.approx(250000.0)
    assert result_high["uninsured"] == pytest.approx(70000.0)

    # IRA balance below SMDIA → fully insured
    result_low = calculate_fdic_coverage(
        orc_code          = "IRA_Traditional",
        balance           = Decimal("75000.00"),
        owner_count       = 1,
        beneficiary_count = 0,
    )
    assert result_low["insured"]   == pytest.approx(75000.0)
    assert result_low["uninsured"] == pytest.approx(0.0)

    # Confirm the ORC code is preserved in the result
    assert result_high["orc"] == "IRA_Traditional"
    assert "330.14" in result_high["rule_applied"]


@pytest.mark.asyncio
async def test_control_a1_detects_missing_orc(db: AsyncSession) -> None:
    """
    Verify that Control A1 surfaces accounts that have no ORC classification.

    Per FDIC Part 370 § 370.3(b): every active/dormant account must have an
    ORC code assigned on the account_open_date.  An account without a
    classification row is a critical compliance gap.
    """
    party = await make_party(db, ssn="333000222")
    acct  = await make_account(db, party.party_id, "Checking", Decimal("5000.00"))
    # Deliberately DO NOT insert an account_regulatory_classification row

    failures = await control_a1_orc_assignment(db)
    account_ids = [str(f["account_id"]) for f in failures]
    assert str(acct.account_id) in account_ids, (
        "Control A1 should flag the account with no ORC classification row."
    )


@pytest.mark.asyncio
async def test_control_b1_detects_gl_variance(db: AsyncSession) -> None:
    """
    Verify that Control B1 detects a daily balance snapshot where
    closing_balance != (opening + deposits - withdrawals + interest - fees).

    Per FDIC Part 370 § 360.8: daily balance snapshots must reconcile exactly
    (within ±$0.01 tolerance) to support accurate insurance determination.
    """
    from sqlalchemy.orm import DeclarativeBase
    from orc_engine import Base

    party = await make_party(db, ssn="444000333")
    acct  = await make_account(db, party.party_id, "Savings", Decimal("20000.00"))

    # Insert a daily balance with an intentional $5 variance
    await db.execute(
        text(
            """
            INSERT INTO daily_account_balance (
              account_id, balance_as_of_date,
              balance_opening_amount, balance_deposits_amount, balance_withdrawals_amount,
              balance_interest_amount, balance_fees_amount, balance_corrections_amount,
              balance_closing_amount, gl_reconciliation_variance, gl_reconciliation_status,
              created_by
            ) VALUES (
              :acct_id, CURRENT_DATE - 0,
              20000.00, 0.00, 0.00, 1.00, 0.00, 0.00,
              20010.00, 9.00, 'Exception',
              'test_runner'
            )
            """
        ),
        {"acct_id": str(acct.account_id)},
    )
    await db.flush()

    failures = await control_b1_daily_balance(db)
    account_ids = [str(f["account_id"]) for f in failures]
    assert str(acct.account_id) in account_ids, (
        "Control B1 should flag the account with a closing balance variance."
    )
    matched = next(f for f in failures if str(f["account_id"]) == str(acct.account_id))
    assert abs(float(matched["variance"])) > 0.01


@pytest.mark.asyncio
async def test_control_c2_detects_wrong_coverage(db: AsyncSession) -> None:
    """
    Verify that Control C2 surfaces a deposit_insurance_calculation where
    calculated_insured_amount > $250,000 for a Single-owner account.

    Per FDIC Part 330 § 330.9: the maximum insured amount for a single-owner
    account is $250,000 regardless of balance.
    """
    party = await make_party(db, ssn="555000444")
    acct  = await make_account(db, party.party_id, "Savings", Decimal("300000.00"))
    cls   = await make_classification(db, acct.account_id, orc_code="Single")

    # Intentionally insert an incorrect calculation (insured > SMDIA for Single)
    await db.execute(
        text(
            """
            INSERT INTO deposit_insurance_calculation (
              account_id, classification_id,
              calculation_date, calculation_scenario,
              input_account_balance, input_accrued_interest,
              input_owner_count, input_orc,
              part_330_rules_version_date, part_330_rules_smdia_amount,
              calculated_insured_amount, calculated_uninsured_amount,
              calculation_test_result
            ) VALUES (
              :acct_id, :cls_id,
              CURRENT_DATE, 'Normal',
              300000.00, 0.00,
              1, 'Single',
              '2023-01-01', 250000.00,
              300000.00, 0.00,
              'Pass'
            )
            """
        ),
        {"acct_id": str(acct.account_id), "cls_id": str(cls.classification_id)},
    )
    await db.flush()

    failures = await control_c2_coverage_calculation(db)
    account_ids = [str(f["account_id"]) for f in failures]
    assert str(acct.account_id) in account_ids, (
        "Control C2 should flag Single account with insured_amount > $250,000."
    )
    matched = next(f for f in failures if str(f["account_id"]) == str(acct.account_id))
    assert "250,000" in matched["failure_reason"] or "single" in matched["failure_reason"].lower()


@pytest.mark.asyncio
async def test_audit_log_trigger_fires_on_update(db: AsyncSession) -> None:
    """
    Verify that the audit log trigger records a row in audit_log when a party
    record is updated.

    Per FDIC Part 370 § 370.3 and 12 U.S.C. § 1831p-1: all modifications to
    key data must be captured with before/after values, the responsible user,
    and the timestamp.

    NOTE: This test requires 04_AUDIT_TRIGGER.sql to be installed in the test DB.
    If the trigger is not installed, the test is skipped.
    """
    # Check if trigger is installed
    trigger_exists_result = await db.execute(
        text(
            """
            SELECT 1 FROM information_schema.triggers
            WHERE trigger_name = 'trg_audit_party'
            LIMIT 1
            """
        )
    )
    if trigger_exists_result.scalar_one_or_none() is None:
        pytest.skip("Audit trigger trg_audit_party not installed — skipping trigger test.")

    # Set the session user for the audit trigger
    await db.execute(text("SELECT set_audit_user('test_runner')"))

    # Create a party
    party = await make_party(db, given="Trigger", family="TestUser", ssn="666000555")
    party_id_str = str(party.party_id)

    # Clear any INSERT audit rows for this party from this txn
    await db.execute(
        text("DELETE FROM audit_log WHERE table_name = 'party' AND primary_key_value = :pk"),
        {"pk": party_id_str},
    )

    # Perform an UPDATE that the trigger will capture
    await db.execute(
        text(
            """
            UPDATE party
               SET individual_name_family = 'TestUser-Updated',
                   modified_by            = 'test_runner',
                   modified_date          = CURRENT_TIMESTAMP
             WHERE party_id = :pk
            """
        ),
        {"pk": party_id_str},
    )
    await db.flush()

    # Verify audit_log has an UPDATE row for the family name change
    audit_result = await db.execute(
        text(
            """
            SELECT column_name, old_value, new_value, change_type, changed_by
            FROM   audit_log
            WHERE  table_name         = 'party'
              AND  primary_key_value  = :pk
              AND  change_type        = 'UPDATE'
              AND  column_name        = 'individual_name_family'
            LIMIT  1
            """
        ),
        {"pk": party_id_str},
    )
    audit_row = audit_result.mappings().first()

    assert audit_row is not None, "Audit trigger did not insert a row into audit_log."
    assert audit_row["old_value"]  == "TestUser"
    assert audit_row["new_value"]  == "TestUser-Updated"
    assert audit_row["change_type"] == "UPDATE"
    assert audit_row["changed_by"]  == "test_runner"
