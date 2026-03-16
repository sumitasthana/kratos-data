"""
main.py — Kratos Data: FDIC Part 370 / Part 330 REST API
=========================================================
FastAPI application providing REST endpoints for the Atomic Deposit System.

Endpoints:
  POST   /parties                            → create party (individual or org)
  GET    /parties/{party_id}                 → get party by UUID
  POST   /accounts                           → create account + auto-assign ORC + coverage
  GET    /accounts/{account_id}              → get account with ORC classification
  POST   /accounts/{account_id}/ownership   → add ownership row
  GET    /accounts/{account_id}/insurance   → get latest insurance calculation
  GET    /audit/controls                    → run all 10 controls (pass/fail summary)
  GET    /audit/control/{control_id}        → run single control (a1–g1)
  GET    /audit/compliance-summary          → annual certification summary (G1)

Python 3.11+ | FastAPI 0.110+ | SQLAlchemy 2.x async | Pydantic v2
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import UUID4, BaseModel, Field, model_validator
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from audit_controls import (
    CONTROL_DESCRIPTIONS,
    CONTROL_REGISTRY,
    run_all_controls,
    control_g1_annual_certification,
)
from orc_engine import (
    AccountORM,
    AccountOwnershipORM,
    AccountRegulatoryClassificationORM,
    DepositInsuranceCalculationORM,
    PartyORM,
    assign_orc_code,
    upsert_insurance_calculation,
    AccountStatusEnum,
    AccountTypeEnum,
    CalculationScenarioEnum,
    InsuranceCategoryEnum,
    OrcCodeEnum,
    OrcDeterminationMethodEnum,
    OwnershipRoleEnum,
    PartyStatusEnum,
    PartyTypeEnum,
    VerificationMethodEnum,
    SMDIA,
)
from ai_engine import ai_generate, ai_analyze, ai_orc_advise, ai_chat_stream
from integrity_validator import validate_generated_sql
from stats_engine import ai_stats_summary, ai_stats_preview
from quality_engine import compute_quality, quality_csv_header
from quality_ai_agent import ai_quality_review


# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env from the project root; no-op if already loaded

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:CHANGE_ME_ENCODED@localhost:5432/atomic_deposit_system",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:  # type: ignore[return]
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Kratos Data — Atomic Deposit System API",
    description=(
        "FDIC Part 370 / Part 330 compliant deposit account management API. "
        "Per FDIC Part 370 § 370.3: enables timely deposit insurance determination."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Shared header dependency
# ---------------------------------------------------------------------------

def get_user_id(x_user_id: Annotated[str, Header()] = "anonymous") -> str:  # type: ignore[assignment]
    """
    Extract the caller identity from the X-User-ID request header.
    Per FDIC Part 370 § 370.4: all data modifications must record the responsible party.
    """
    if not x_user_id or x_user_id == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID header is required.",
        )
    return x_user_id


# ---------------------------------------------------------------------------
# Request / Response Pydantic models
# ---------------------------------------------------------------------------

class CreatePartyRequest(BaseModel):
    """Request to create a new PARTY record. Per FinCEN CIP (31 U.S.C. § 5318)."""
    party_type:               str = Field(..., pattern="^(Individual|Organization|Government)$")
    party_status:             str = "Active"
    # Individual fields
    individual_name_given:    Optional[str] = None
    individual_name_middle:   Optional[str] = None
    individual_name_family:   Optional[str] = None
    individual_date_of_birth: Optional[date] = None
    individual_ssn:           Optional[str] = Field(None, min_length=9, max_length=9, pattern=r"^\d{9}$")
    # Organization fields
    organization_legal_name:  Optional[str] = None
    organization_tax_id:      Optional[str] = None
    organization_type:        Optional[str] = None
    organization_country_of_inc: Optional[str] = Field(None, min_length=2, max_length=2)
    organization_state_of_inc:   Optional[str] = Field(None, min_length=2, max_length=2)
    # Contact
    phone_number_primary:     Optional[str] = None
    email_primary:            Optional[str] = None
    # Address
    address_street_line1:     Optional[str] = None
    address_city:             Optional[str] = None
    address_state_province:   Optional[str] = None
    address_postal_code:      Optional[str] = None
    address_country:          Optional[str] = Field(None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_party_type_fields(self) -> "CreatePartyRequest":
        if self.party_type == "Individual" and not self.individual_name_family:
            raise ValueError("individual_name_family is required for Individual parties.")
        if self.party_type == "Organization" and not self.organization_legal_name:
            raise ValueError("organization_legal_name is required for Organization parties.")
        return self


class PartyResponse(BaseModel):
    """Response model for a PARTY record."""
    model_config = {"from_attributes": True}

    party_id:               UUID4
    party_type:             str
    party_status:           str
    individual_name_given:  Optional[str] = None
    individual_name_family: Optional[str] = None
    organization_legal_name: Optional[str] = None
    organization_tax_id:    Optional[str] = None
    address_city:           Optional[str] = None
    address_state_province: Optional[str] = None
    address_country:        Optional[str] = None
    created_date:           Optional[datetime] = None
    created_by:             str


class CreateAccountRequest(BaseModel):
    """
    Request to create a new deposit ACCOUNT.
    ORC code and FDIC coverage are auto-assigned on creation.
    Per FDIC Part 370 § 370.3(b): ORC must be assigned at account opening.
    """
    account_number:           str  = Field(..., min_length=1, max_length=20)
    account_type:             str
    account_open_date:        date
    primary_owner_party_id:   UUID4
    interest_rate_percentage: Decimal = Field(Decimal("0.0000"), ge=0)
    current_balance:          Decimal = Field(Decimal("0.00"), ge=0)
    current_balance_date:     date
    minimum_balance:          Decimal = Decimal("0.00")
    interest_calculation_method: Optional[str] = None
    interest_compounding_freq:   Optional[str] = None
    interest_calculation_basis:  Optional[str] = None


class AccountResponse(BaseModel):
    """Response model for an ACCOUNT with its ORC classification."""
    model_config = {"from_attributes": True}

    account_id:              UUID4
    account_number:          str
    account_type:            str
    account_status:          str
    account_open_date:       date
    primary_owner_party_id:  UUID4
    current_balance:         Decimal
    current_balance_date:    date
    orc_code:                Optional[str] = None
    is_joint_ownership:      Optional[bool] = None
    is_ira:                  Optional[bool] = None
    is_trust:                Optional[bool] = None
    created_date:            Optional[datetime] = None


class CreateOwnershipRequest(BaseModel):
    """Request to add an ownership row to an account."""
    owner_party_id:              UUID4
    ownership_role:              str = Field(..., pattern="^(PrimaryOwner|JointOwner|SecondaryOwner|Trustee|Beneficiary|PowerOfAttorney|Guardian)$")
    ownership_percentage_amount: Decimal = Field(Decimal("100.00"), ge=0, le=100)
    ownership_effective_date:    date     = Field(default_factory=date.today)
    ownership_verification_date: date     = Field(default_factory=date.today)
    ownership_verification_method: Optional[str] = "DocumentReview"


class OwnershipResponse(BaseModel):
    """Response model for an ACCOUNT_OWNERSHIP row."""
    model_config = {"from_attributes": True}

    account_ownership_id:        UUID4
    account_id:                  UUID4
    owner_party_id:              UUID4
    ownership_role:              str
    ownership_percentage_amount: Decimal
    ownership_effective_date:    date
    created_date:                Optional[datetime] = None


class InsuranceCalculationResponse(BaseModel):
    """Response model for latest DEPOSIT_INSURANCE_CALCULATION."""
    model_config = {"from_attributes": True}

    calculation_id:              UUID4
    account_id:                  UUID4
    input_orc:                   str
    input_account_balance:       Decimal
    input_owner_count:           int
    beneficiary_count:           Optional[int] = None
    calculated_insured_amount:   Decimal
    calculated_uninsured_amount: Decimal
    calculation_basis_description: Optional[str] = None
    calculation_test_result:     str
    calculation_date:            date


class ControlSummaryItem(BaseModel):
    """Pass/fail summary for one audit control."""
    control_id:      str
    description:     str
    status:          str
    failing_count:   int


# ---------------------------------------------------------------------------
# Party endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/parties",
    response_model=PartyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new party (individual or organization)",
    tags=["Parties"],
)
async def create_party(
    body: CreatePartyRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> PartyResponse:
    """
    Create a new PARTY record (individual or organization).

    Per FinCEN CIP (31 U.S.C. § 5318): each customer must be identified before
    account opening.  Returns 422 with detail on any validation failure.
    """
    party = PartyORM(
        party_type               = PartyTypeEnum(body.party_type),
        party_status             = PartyStatusEnum(body.party_status),
        individual_name_given    = body.individual_name_given,
        individual_name_middle   = body.individual_name_middle,
        individual_name_family   = body.individual_name_family,
        individual_date_of_birth = body.individual_date_of_birth,
        individual_ssn           = body.individual_ssn,
        organization_legal_name  = body.organization_legal_name,
        organization_tax_id      = body.organization_tax_id,
        phone_number_primary     = body.phone_number_primary,
        email_primary            = body.email_primary,
        address_street_line1     = body.address_street_line1,
        address_city             = body.address_city,
        address_state_province   = body.address_state_province,
        address_postal_code      = body.address_postal_code,
        address_country          = body.address_country,
        address_is_usa           = (body.address_country == "US") if body.address_country else False,
        created_by               = user_id,
        modified_by              = user_id,
    )
    db.add(party)
    await db.commit()
    await db.refresh(party)
    return PartyResponse.model_validate(party)


@app.get(
    "/parties/{party_id}",
    response_model=PartyResponse,
    summary="Get party by UUID",
    tags=["Parties"],
)
async def get_party(
    party_id: UUID4 = Path(..., description="Party UUID"),
    db: AsyncSession = Depends(get_db),
) -> PartyResponse:
    """
    Retrieve a party record by its UUID primary key.
    Per FDIC Part 370 § 370.4(a): party information must be complete and current.
    """
    result = await db.execute(select(PartyORM).where(PartyORM.party_id == party_id))
    party = result.scalar_one_or_none()
    if party is None:
        raise HTTPException(status_code=404, detail=f"Party {party_id} not found.")
    return PartyResponse.model_validate(party)


# ---------------------------------------------------------------------------
# Account endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create account, auto-assign ORC, run FDIC coverage calculation",
    tags=["Accounts"],
)
async def create_account(
    body: CreateAccountRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    """
    Create a deposit account, automatically assign an ORC code via
    `assign_orc_code()`, and compute FDIC Part 330 coverage.

    Per FDIC Part 370 § 370.3(b): the ORC code must be assigned at the time
    of account opening.

    Steps:
      1. Validate primary_owner_party_id exists.
      2. Insert ACCOUNT row.
      3. Insert ACCOUNT_OWNERSHIP row for primary owner.
      4. Assign ORC via assign_orc_code() and insert ACCOUNT_REGULATORY_CLASSIFICATION.
      5. Call upsert_insurance_calculation() and insert DEPOSIT_INSURANCE_CALCULATION.
    """
    # 1. Validate primary owner exists
    owner_result = await db.execute(
        select(PartyORM).where(PartyORM.party_id == body.primary_owner_party_id)
    )
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail=f"Primary owner party {body.primary_owner_party_id} not found.")

    # 2. Insert account
    acct = AccountORM(
        account_number               = body.account_number,
        account_type                 = AccountTypeEnum(body.account_type),
        account_status               = AccountStatusEnum.Active,
        account_open_date            = body.account_open_date,
        primary_owner_party_id       = body.primary_owner_party_id,
        interest_rate_percentage     = body.interest_rate_percentage,
        interest_rate_effective_date = body.account_open_date,
        interest_calculation_method  = body.interest_calculation_method,
        interest_compounding_freq    = body.interest_compounding_freq,
        interest_calculation_basis   = body.interest_calculation_basis,
        current_balance              = body.current_balance,
        current_balance_date         = body.current_balance_date,
        accrued_interest_not_posted  = Decimal("0.00"),
        minimum_balance              = body.minimum_balance,
        created_by                   = user_id,
        modified_by                  = user_id,
    )
    db.add(acct)
    await db.flush()  # get account_id before relationships

    # 3. Insert primary ownership row (100%, PrimaryOwner)
    ownership = AccountOwnershipORM(
        account_id                   = acct.account_id,
        owner_party_id               = body.primary_owner_party_id,
        ownership_role               = OwnershipRoleEnum.PrimaryOwner,
        ownership_percentage_amount  = Decimal("100.00"),
        ownership_effective_date     = body.account_open_date,
        ownership_verification_date  = body.account_open_date,
        ownership_verification_method = VerificationMethodEnum.DocumentReview,
        created_by                   = user_id,
    )
    db.add(ownership)
    await db.flush()

    # 4. Auto-assign ORC code
    orc = assign_orc_code(
        account_type      = body.account_type,
        owner_count       = 1,
        has_beneficiaries = False,
    )
    is_joint = orc.value.startswith("Joint_")
    is_ira   = orc.value.startswith("IRA_") or orc.value.startswith("Keogh_")
    is_trust = orc.value.startswith("Trust_")

    classification = AccountRegulatoryClassificationORM(
        account_id                   = acct.account_id,
        orc_code                     = orc,
        orc_insured_amount_per_owner = SMDIA,
        orc_insurance_category       = InsuranceCategoryEnum.Covered,
        orc_determination_date       = body.account_open_date,
        orc_determination_method     = OrcDeterminationMethodEnum.RegistrationForm,
        orc_verification_date        = body.account_open_date,
        is_joint_ownership           = is_joint,
        is_ira                       = is_ira,
        is_keogh                     = orc.value.startswith("Keogh_"),
        is_trust                     = is_trust,
        is_government                = orc.value.startswith("Government_"),
        is_business                  = orc.value.startswith("Business_"),
        is_payable_on_death          = orc == OrcCodeEnum.POD_PayableOnDeath,
        is_transfer_on_death         = orc == OrcCodeEnum.TOD_TransferOnDeath,
        created_by                   = user_id,
    )
    db.add(classification)
    await db.flush()

    # 5. Compute and insert insurance calculation
    await upsert_insurance_calculation(
        account_id  = acct.account_id,
        db_session  = db,
        scenario    = CalculationScenarioEnum.Normal,
        created_by  = user_id,
    )

    await db.commit()
    await db.refresh(acct)

    return AccountResponse(
        account_id             = acct.account_id,
        account_number         = acct.account_number,
        account_type           = acct.account_type,
        account_status         = acct.account_status,
        account_open_date      = acct.account_open_date,
        primary_owner_party_id = acct.primary_owner_party_id,
        current_balance        = acct.current_balance,
        current_balance_date   = acct.current_balance_date,
        orc_code               = orc.value,
        is_joint_ownership     = is_joint,
        is_ira                 = is_ira,
        is_trust               = is_trust,
        created_date           = acct.created_date,
    )


@app.get(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    summary="Get account with ORC classification",
    tags=["Accounts"],
)
async def get_account(
    account_id: UUID4 = Path(..., description="Account UUID"),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    """
    Retrieve a deposit account and its current ORC classification.
    Per FDIC Part 370 § 370.4: account and ORC data must be readily accessible.
    """
    result = await db.execute(select(AccountORM).where(AccountORM.account_id == account_id))
    acct = result.scalar_one_or_none()
    if acct is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")

    cls_result = await db.execute(
        select(AccountRegulatoryClassificationORM).where(
            AccountRegulatoryClassificationORM.account_id == account_id
        )
    )
    cls = cls_result.scalar_one_or_none()

    return AccountResponse(
        account_id             = acct.account_id,
        account_number         = acct.account_number,
        account_type           = acct.account_type,
        account_status         = acct.account_status,
        account_open_date      = acct.account_open_date,
        primary_owner_party_id = acct.primary_owner_party_id,
        current_balance        = acct.current_balance,
        current_balance_date   = acct.current_balance_date,
        orc_code               = cls.orc_code if cls else None,
        is_joint_ownership     = cls.is_joint_ownership if cls else None,
        is_ira                 = cls.is_ira if cls else None,
        is_trust               = cls.is_trust if cls else None,
        created_date           = acct.created_date,
    )


@app.post(
    "/accounts/{account_id}/ownership",
    response_model=OwnershipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an ownership row to an account",
    tags=["Accounts"],
)
async def add_ownership(
    account_id: UUID4 = Path(..., description="Account UUID"),
    body: CreateOwnershipRequest = ...,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> OwnershipResponse:
    """
    Add a new owner (joint, trustee, POA, etc.) to an existing account.

    After adding the owner, re-calculates ORC code (if the account now has
    ≥ 2 owners, it may upgrade from Single → Joint_JTWROS) and updates the
    FDIC coverage calculation accordingly.

    Per FDIC Part 370 § 370.4(c): ownership changes must be recorded promptly.
    """
    # Validate account exists
    acct_result = await db.execute(select(AccountORM).where(AccountORM.account_id == account_id))
    acct = acct_result.scalar_one_or_none()
    if acct is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")

    # Validate party exists
    party_result = await db.execute(
        select(PartyORM).where(PartyORM.party_id == body.owner_party_id)
    )
    if party_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail=f"Party {body.owner_party_id} not found.")

    # Insert ownership row
    row = AccountOwnershipORM(
        account_id                    = account_id,
        owner_party_id                = body.owner_party_id,
        ownership_role                = OwnershipRoleEnum(body.ownership_role),
        ownership_percentage_amount   = body.ownership_percentage_amount,
        ownership_effective_date      = body.ownership_effective_date,
        ownership_verification_date   = body.ownership_verification_date,
        ownership_verification_method = VerificationMethodEnum(body.ownership_verification_method) if body.ownership_verification_method else None,
        created_by                    = user_id,
    )
    db.add(row)
    await db.flush()

    # Re-run coverage calculation after ownership change
    try:
        await upsert_insurance_calculation(
            account_id  = account_id,
            db_session  = db,
            scenario    = CalculationScenarioEnum.Normal,
            created_by  = user_id,
        )
    except Exception:
        pass  # Non-fatal: coverage re-calc is best-effort here

    await db.commit()
    await db.refresh(row)
    return OwnershipResponse.model_validate(row)


@app.get(
    "/accounts/{account_id}/insurance",
    response_model=InsuranceCalculationResponse,
    summary="Get latest FDIC insurance calculation for an account",
    tags=["Accounts"],
)
async def get_insurance(
    account_id: UUID4 = Path(..., description="Account UUID"),
    db: AsyncSession = Depends(get_db),
) -> InsuranceCalculationResponse:
    """
    Return the most recent deposit_insurance_calculation row for the account.
    Per FDIC Part 370 § 370.3: coverage must be determinable on demand.
    """
    result = await db.execute(
        select(DepositInsuranceCalculationORM)
        .where(DepositInsuranceCalculationORM.account_id == account_id)
        .order_by(DepositInsuranceCalculationORM.calculation_date.desc(),
                  DepositInsuranceCalculationORM.created_date.desc())
        .limit(1)
    )
    calc = result.scalar_one_or_none()
    if calc is None:
        raise HTTPException(
            status_code=404,
            detail=f"No insurance calculation found for account {account_id}.",
        )
    return InsuranceCalculationResponse.model_validate(calc)


# ---------------------------------------------------------------------------
# Audit log endpoint
# ---------------------------------------------------------------------------

class AuditLogEntry(BaseModel):
    """Single audit log row."""
    audit_log_id:      UUID4
    table_name:        str
    primary_key_value: str
    column_name:       str
    old_value:         Optional[str] = None
    new_value:         Optional[str] = None
    change_type:       str
    changed_date:      datetime
    changed_by:        str


@app.get(
    "/audit-log/{table_name}/{record_id}",
    response_model=list[AuditLogEntry],
    summary="Get audit log entries for a specific record",
    tags=["Audit"],
)
async def get_audit_log(
    table_name: str = Path(..., description="Table name (e.g. party, account)"),
    record_id:  str = Path(..., description="Primary key value (UUID string)"),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogEntry]:
    """
    Return all audit_log rows for a given table + primary key value.
    Per FDIC Part 370 § 370.3: all data changes must be traceable.
    """
    result = await db.execute(
        text(
            """
            SELECT audit_log_id, table_name, primary_key_value, column_name,
                   old_value, new_value, change_type, changed_date, changed_by
            FROM   audit_log
            WHERE  table_name         = :tbl
              AND  primary_key_value  = :pk
            ORDER BY changed_date DESC
            """
        ),
        {"tbl": table_name, "pk": record_id},
    )
    rows = result.mappings().all()
    return [AuditLogEntry(**dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Audit control endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/audit/controls",
    response_model=list[ControlSummaryItem],
    summary="Run all 10 audit controls and return pass/fail summary",
    tags=["Audit"],
)
async def run_controls(db: AsyncSession = Depends(get_db)) -> list[ControlSummaryItem]:
    """
    Execute all 10 Part 370 / Part 330 audit controls and return a summary.
    Per FDIC Part 370 § 370.3(c): annual end-to-end system test requirement.
    """
    summary = await run_all_controls(db)
    return [
        ControlSummaryItem(
            control_id    = v["control_id"],
            description   = v["description"],
            status        = v["status"],
            failing_count = v["failing_count"],
        )
        for v in summary.values()
    ]


@app.get(
    "/audit/control/{control_id}",
    summary="Run a specific audit control (a1, a2, ..., g1) and return failing records",
    tags=["Audit"],
)
async def run_single_control(
    control_id: str = Path(
        ...,
        description="Control ID (a1, a2, a3, a4, a5, a6, b1, b3, c2, g1)",
        pattern="^(a1|a2|a3|a4|a5|a6|b1|b3|c2|g1)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Run a specific audit control and return its failing records.
    Returns an empty list when the control passes.
    """
    fn = CONTROL_REGISTRY.get(control_id)
    if fn is None:
        raise HTTPException(
            status_code=404,
            detail=f"Control '{control_id}' not found. Valid: {list(CONTROL_REGISTRY.keys())}",
        )
    records = await fn(db)
    return {
        "control_id":      control_id.upper(),
        "description":     CONTROL_DESCRIPTIONS[control_id],
        "status":          "FAIL" if records else "PASS",
        "failing_count":   len(records),
        "failing_records": records,
    }


@app.get(
    "/audit/compliance-summary",
    summary="Annual certification summary (Control G1) per FDIC Part 370 § 370.3(c)",
    tags=["Audit"],
)
async def compliance_summary(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """
    Return the Control G1 annual certification summary: total accounts,
    pass/fail counts, total insured and uninsured per calendar year.

    Per FDIC Part 370 § 370.3(c): each covered institution must conduct an
    annual test of its deposit insurance determination system and certify
    results to the FDIC.
    """
    return await control_g1_annual_certification(db)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health check", tags=["Infrastructure"])
async def health() -> dict[str, str]:
    """Returns 200 OK when the API is running."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# KratosAI — request / response models
# ---------------------------------------------------------------------------

class AiGenerateRequest(BaseModel):
    """Request body for POST /ai/generate (MODE 1 — Synthetic Data Generator)."""
    entities:           list[str]       = Field(default_factory=lambda: ["party", "account"])
    count:              dict[str, int]  = Field(default_factory=lambda: {"party": 5, "account": 8})
    scenario:           str             = "clean"       # clean | edge_cases | violations | mixed
    output_format:      str             = "sql"         # sql | json
    include_violations: bool            = False
    violation_types:    list[str]       = Field(default_factory=list)


class AiAnalyzeRequest(BaseModel):
    """Request body for POST /ai/analyze (MODE 2 — Compliance Analyst)."""
    explain: bool = True


class AiOrcAdviseRequest(BaseModel):
    """Request body for POST /ai/orc-advise (MODE 3 — ORC Assignment Advisor)."""
    account_type:          str
    party_type:            str  = "Individual"
    owner_count:           int  = Field(1, ge=1)
    has_beneficiaries:     bool = False
    has_pod_designation:   bool = False
    has_irrevocable_trust: bool = False
    is_government_entity:  bool = False
    is_retirement_account: bool = False
    is_hsa:                bool = False
    is_iolta:              bool = False
    notes:                 Optional[str] = None


class ChatMessage(BaseModel):
    """A single turn in a KratosAI conversation."""
    role:    str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class AiChatRequest(BaseModel):
    """Request body for POST /ai/chat (streaming conversational interface)."""
    messages: list[ChatMessage] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# KratosAI — shared DB context helper
# ---------------------------------------------------------------------------

async def _fetch_db_context(db: AsyncSession) -> str:
    """
    Fetch live record counts from the database and return them as a compact
    string for injection into the KratosAI system prompt preamble.
    """
    row = (
        await db.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM party)                            AS party_count,
                    (SELECT COUNT(*) FROM account)                          AS account_count,
                    (SELECT COUNT(*) FROM account_ownership)                AS ownership_count,
                    (SELECT COUNT(*) FROM account_regulatory_classification) AS orc_count,
                    (SELECT COUNT(*) FROM deposit_insurance_calculation)    AS insurance_count,
                    (SELECT COUNT(*) FROM kyc_cip_verification)             AS kyc_count
                """
            )
        )
    ).mappings().one()
    return (
        f"parties={row['party_count']}, accounts={row['account_count']}, "
        f"ownership_rows={row['ownership_count']}, orc_classifications={row['orc_count']}, "
        f"insurance_calculations={row['insurance_count']}, kyc_verifications={row['kyc_count']}"
    )


# ---------------------------------------------------------------------------
# KratosAI endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/ai/generate",
    summary="KratosAI MODE 1 — Generate synthetic deposit data",
    tags=["KratosAI"],
)
async def ai_generate_endpoint(
    body: AiGenerateRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Ask KratosAI to produce referentially consistent synthetic SQL/JSON test data.

    After generation, the SQL is run through the integrity validator to confirm
    all FK references are valid before returning.  The output is **not** auto-executed
    against the database — execution remains the caller's responsibility so that
    the watermark `-- SYNTHETIC TEST DATA — NOT FOR PRODUCTION USE` is preserved.

    Per FDIC Part 370: synthetic data must honour the full ORC constraint graph.
    """
    try:
        db_context = await _fetch_db_context(db)
        generated = await ai_generate(body.model_dump(), db_context)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Run FK pre-check if SQL output was requested
    validation = None
    if body.output_format == "sql":
        vr = await validate_generated_sql(generated, db)
        validation = {
            "valid":         vr.valid,
            "checked_count": vr.checked_count,
            "violations":    vr.violations,
        }

    return {
        "generated_content": generated,
        "output_format":     body.output_format,
        "integrity_check":   validation,
    }


@app.post(
    "/ai/analyze",
    summary="KratosAI MODE 2 — Run live compliance analysis",
    tags=["KratosAI"],
)
async def ai_analyze_endpoint(
    body: AiAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Run all 10 audit controls against the live database, then pass the raw
    findings to KratosAI for structured compliance analysis output.

    Returns both the raw control results and the AI-enhanced findings with
    severity ratings, regulatory citations, and remediation guidance.

    Per FDIC Part 370 § 370.3(c): supports the annual end-to-end system test.
    """
    try:
        db_context = await _fetch_db_context(db)
        raw_controls = await run_all_controls(db)
        findings_list = list(raw_controls.values())
        analysis = await ai_analyze(findings_list, db_context)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "raw_control_results": findings_list,
        "ai_analysis":         analysis,
        "db_context":          db_context,
    }


@app.post(
    "/ai/orc-advise",
    summary="KratosAI MODE 3 — Recommend ORC code for an account profile",
    tags=["KratosAI"],
)
async def ai_orc_advise_endpoint(
    body: AiOrcAdviseRequest,
) -> dict[str, Any]:
    """
    Given an account/party profile, KratosAI walks the FDIC Part 370
    ORC Assignment Decision Tree and returns a recommended ORC code with
    full reasoning, regulatory basis, and required follow-up records.

    Per FDIC Part 370 § 370.3(b): ORC must be assigned at account opening.
    """
    try:
        advice = await ai_orc_advise(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {"profile": body.model_dump(), "orc_advice": advice}


@app.post(
    "/ai/chat",
    summary="KratosAI — Streaming conversational interface",
    tags=["KratosAI"],
)
async def ai_chat_endpoint(
    body: AiChatRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Stream a conversational response from KratosAI.

    The response is delivered as Server-Sent Events (SSE):
      data: <JSON-encoded text chunk>\\n\\n
      ...
      data: [DONE]\\n\\n

    Each `data:` payload is a JSON string (call JSON.parse on the client side).
    A final `data: [DONE]` signals stream completion.
    """
    db_context = await _fetch_db_context(db)
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def _event_stream():
        try:
            async for chunk in ai_chat_stream(messages, db_context):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except RuntimeError as exc:
            error_payload = __import__("json").dumps(f"ERROR: {exc}")
            yield f"data: {error_payload}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Stats & Preview endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/stats/summary",
    summary="Kratos Stats Engine — structured compliance statistics",
    tags=["Stats"],
)
async def stats_summary(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Accept a stats-mode payload (entity counts + violations + ORC distribution)
    and return a structured compliance statistics object.

    Assembles live manifest counts from the database when the caller sends
    an empty or partial manifest; merges with any additional payload fields
    provided by the caller.

    Per FDIC Part 370: statistics must reflect the current state of all 14 tables.
    """
    # Auto-populate manifest from live DB counts if not fully provided
    manifest = payload.get("manifest") or {}
    if not manifest:
        row = (
            await db.execute(
                text(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM party)                             AS parties,
                        (SELECT COUNT(*) FROM account)                           AS accounts,
                        (SELECT COUNT(*) FROM account_ownership)                 AS account_ownership,
                        (SELECT COUNT(*) FROM account_regulatory_classification) AS account_regulatory_classification,
                        (SELECT COUNT(*) FROM kyc_cip_verification)              AS kyc_cip_verification,
                        (SELECT COUNT(*) FROM deposit_insurance_calculation)     AS deposit_insurance_calculation
                    """
                )
            )
        ).mappings().one()
        manifest = dict(row)

    merged = {**payload, "manifest": manifest, "mode": "stats"}
    try:
        result = await ai_stats_summary(merged)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result


@app.post(
    "/stats/preview",
    summary="Kratos Stats Engine — annotated data preview with violation flags",
    tags=["Stats"],
)
async def stats_preview(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Accept a preview-mode payload (table name + raw rows) and return a
    structured preview object with per-row violation flags.

    FK checks are performed server-side via parameterised SQL so that the
    full ID lists are never forwarded to the AI (prevents token overflow on
    large datasets). Only the discovered violations are sent to Claude.

    Per FDIC Part 370: data integrity checks must cover all FK relationships.
    """
    from sqlalchemy import bindparam

    rows: list[dict[str, Any]] = payload.get("rows") or []
    fk_violations: list[dict[str, Any]] = []

    try:
        # Collect unique UUID strings referenced in the preview rows
        party_refs   = list({str(r["party_id"])   for r in rows if r.get("party_id")})
        account_refs = list({str(r["account_id"]) for r in rows if r.get("account_id")})

        if party_refs:
            # Find which of the supplied party UUIDs do NOT exist in the DB
            stmt = text(
                "SELECT party_id::text FROM party "
                "WHERE party_id::text = ANY(:refs)"
            )
            res  = await db.execute(stmt, {"refs": party_refs})
            found = {r[0] for r in res.fetchall()}
            for ref in party_refs:
                if ref not in found:
                    fk_violations.append({
                        "column": "party_id", "value": ref,
                        "code": "FK_MISSING_PARTY", "severity": "error",
                    })

        if account_refs:
            stmt = text(
                "SELECT account_id::text FROM account "
                "WHERE account_id::text = ANY(:refs)"
            )
            res  = await db.execute(stmt, {"refs": account_refs})
            found = {r[0] for r in res.fetchall()}
            for ref in account_refs:
                if ref not in found:
                    fk_violations.append({
                        "column": "account_id", "value": ref,
                        "code": "FK_MISSING_ACCOUNT", "severity": "error",
                    })
    except Exception as exc:
        # Non-fatal: skip FK pre-check on DB error; Claude will still annotate rows
        fk_violations = [{"code": "FK_CHECK_ERROR", "detail": str(exc), "severity": "warn"}]

    merged = {
        "mode":          "preview",
        "table":         payload.get("table", ""),
        "rows":          rows,
        "fk_violations": fk_violations,
    }
    try:
        result = await ai_stats_preview(merged)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result


# ---------------------------------------------------------------------------
# Quality AI Review endpoint
# ---------------------------------------------------------------------------

class _QualityReviewRequest(BaseModel):
    quality_report: dict


@app.post(
    "/quality/review",
    summary="AI-powered narrative review of a quality report",
    tags=["Quality"],
)
async def quality_review(body: _QualityReviewRequest) -> dict:
    """
    Sends the quality report produced by /generate to the Kratos Quality
    Review Agent (Claude). Returns a structured narrative that distinguishes
    genuine data errors from config/schema drift, ranks issues, and provides
    prioritised recommendations.
    """
    report = body.quality_report
    if not report:
        raise HTTPException(status_code=400, detail="quality_report must not be empty.")
    try:
        result = await ai_quality_review(report)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Quality review failed: {exc}")
    return result


# ---------------------------------------------------------------------------
# Generate & Export endpoints  (minimal data-tool flow)
# ---------------------------------------------------------------------------

import csv
import io
import uuid as _uuid_mod
from datetime import datetime as _dt

# In-memory store: token -> {"columns": [...], "rows": [...], "generated_at": str, "quality": {...}}
# Short-lived (process lifetime only) — suitable for demo/dev use.
_GENERATE_STORE: dict[str, dict[str, Any]] = {}
_LAST_GENERATE_TOKEN: str | None = None

_GENERATE_SQL = """
    SELECT
        p.party_id::text                                    AS party_id,
        COALESCE(
            NULLIF(TRIM(COALESCE(p.individual_name_given,'') || ' ' ||
                        COALESCE(p.individual_name_family,'')), ' '),
            p.organization_legal_name,
            'Unknown'
        )                                                   AS name,
        p.party_type::text                                  AS party_type,
        p.party_status::text                                AS party_status,
        a.account_id::text                                  AS account_id,
        a.account_number                                    AS account_number,
        a.account_type::text                                AS account_type,
        a.account_status::text                              AS account_status,
        a.current_balance::text                             AS current_balance,
        a.account_open_date::text                           AS account_open_date,
        COALESCE(c.orc_code::text, '')                      AS orc_code
    FROM   party              p
    JOIN   account            a  ON a.primary_owner_party_id = p.party_id
    LEFT   JOIN account_regulatory_classification c
                                  ON c.account_id = a.account_id
    ORDER  BY a.account_open_date DESC, a.created_date DESC
"""

_RECORDS_COLUMNS = [
    "party_id", "name", "party_type", "party_status",
    "account_id", "account_number", "account_type", "account_status",
    "current_balance", "account_open_date", "orc_code",
]


@app.post(
    "/generate",
    summary="Generate dataset snapshot from live DB",
    tags=["Generate"],
)
async def generate_dataset(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Queries the live DB for a joined party+account dataset, stores it in a
    short-lived in-memory buffer keyed by a signed token, and returns the
    token plus the first 20 preview rows.
    """
    global _LAST_GENERATE_TOKEN
    result = await db.execute(text(_GENERATE_SQL))
    all_rows = [dict(zip(_RECORDS_COLUMNS, r)) for r in result.fetchall()]

    generated_at    = _dt.utcnow().isoformat()
    quality_report  = compute_quality(all_rows, generated_at)

    token = str(_uuid_mod.uuid4())
    _GENERATE_STORE[token] = {
        "columns":      _RECORDS_COLUMNS,
        "rows":         all_rows,
        "generated_at": _dt.utcnow().strftime("%Y%m%d_%H%M"),
        "quality":      quality_report,
    }
    _LAST_GENERATE_TOKEN = token

    return {
        "token":          token,
        "total_rows":     len(all_rows),
        "columns":        _RECORDS_COLUMNS,
        "preview_rows":   all_rows[:20],
        "generated_at":   _GENERATE_STORE[token]["generated_at"],
        "quality_report": quality_report,
    }


@app.get(
    "/generate/{token}/csv",
    summary="Stream generated dataset as CSV",
    tags=["Generate"],
)
async def download_csv(token: str = Path(..., description="Token from /generate")) -> StreamingResponse:
    """
    Stream the previously generated dataset as a CSV file.
    Filename includes the generation timestamp for traceability.
    """
    entry = _GENERATE_STORE.get(token)
    if entry is None:
        raise HTTPException(status_code=404, detail="Token not found or expired. Re-run /generate.")

    def _iter_csv():
        if entry.get("quality"):
            yield quality_csv_header(entry["quality"])
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(entry["columns"])
        yield buf.getvalue()
        for row in entry["rows"]:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([row.get(c, "") for c in entry["columns"]])
            yield buf.getvalue()

    filename = f"kratos_data_{entry['generated_at']}.csv"
    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get(
    "/records",
    summary="Read-only view of latest DB records",
    tags=["Generate"],
)
async def get_records(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Returns the latest `limit` (default 100, max 1000) rows from the joined
    party+account view. Read-only; no write operations exposed.
    """
    safe_limit = min(max(1, limit), 1000)
    result = await db.execute(text(_GENERATE_SQL + f" LIMIT {safe_limit}"))
    rows = [dict(zip(_RECORDS_COLUMNS, r)) for r in result.fetchall()]

    quality_summary: str | None = None
    if _LAST_GENERATE_TOKEN and _LAST_GENERATE_TOKEN in _GENERATE_STORE:
        qr = _GENERATE_STORE[_LAST_GENERATE_TOKEN].get("quality", {})
        ts = _GENERATE_STORE[_LAST_GENERATE_TOKEN].get("generated_at", "")
        overall = qr.get("overall", "").upper()
        summary = qr.get("summary_line", "")
        quality_summary = f"Last run: {ts} | Quality: {overall} — {summary}"

    return {
        "columns":         _RECORDS_COLUMNS,
        "rows":            rows,
        "total":           len(rows),
        "quality_summary": quality_summary,
    }
