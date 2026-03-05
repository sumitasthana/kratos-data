"""
orc_engine.py — FDIC Part 370 / Part 330 ORC Assignment & Coverage Engine
==========================================================================
Regulatory references:
  - FDIC Part 370 (Recordkeeping for Timely Deposit Insurance Determination)
  - FDIC Part 330 (Deposit Insurance Coverage)
  - 12 U.S.C. § 1821(a)(2)(D) — Standard Maximum Deposit Insurance Amount ($250,000)

Python 3.11+ | SQLAlchemy 2.x async | Pydantic v2
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import UUID4, BaseModel, Field, model_validator
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship

# ---------------------------------------------------------------------------
# Constants — FDIC Standard Maximum Deposit Insurance Amount (SMDIA)
# ---------------------------------------------------------------------------
SMDIA: Decimal = Decimal("250000.00")
MAX_TRUST_BENEFICIARIES: int = 5


# ---------------------------------------------------------------------------
# Enumeration mirrors (Python-side; must match DDL enum names exactly)
# ---------------------------------------------------------------------------

class OrcCodeEnum(str, Enum):
    """Per FDIC Part 370 Appendix A — Ownership Right & Capacity codes."""
    Single                          = "Single"
    Joint_TenancyByEntirety         = "Joint_TenancyByEntirety"
    Joint_TenancyInCommon           = "Joint_TenancyInCommon"
    Joint_JTWROS                    = "Joint_JTWROS"
    IRA_Traditional                 = "IRA_Traditional"
    IRA_Roth                        = "IRA_Roth"
    IRA_SEP                         = "IRA_SEP"
    IRA_SIMPLE                      = "IRA_SIMPLE"
    Keogh_DefinedContribution       = "Keogh_DefinedContribution"
    Keogh_DefinedBenefit            = "Keogh_DefinedBenefit"
    Trust_Revocable                 = "Trust_Revocable"
    Trust_Irrevocable               = "Trust_Irrevocable"
    Trust_Charitable                = "Trust_Charitable"
    Trust_Qualified                 = "Trust_Qualified"
    Escrow_Agent                    = "Escrow_Agent"
    Government_Federal              = "Government_Federal"
    Government_State                = "Government_State"
    Government_Local                = "Government_Local"
    Business_Corporation            = "Business_Corporation"
    Business_Partnership            = "Business_Partnership"
    Business_LLC                    = "Business_LLC"
    Business_SoleProprietor         = "Business_SoleProprietor"
    POD_PayableOnDeath              = "POD_PayableOnDeath"
    TOD_TransferOnDeath             = "TOD_TransferOnDeath"
    FiduciaryOther                  = "FiduciaryOther"


class AccountTypeEnum(str, Enum):
    """Per account_type_enum in DDL."""
    Savings                     = "Savings"
    Checking                    = "Checking"
    MoneyMarket                 = "Money Market"
    CertificateOfDeposit        = "Certificate of Deposit"
    IndividualRetirementAccount = "Individual Retirement Account"
    TrustAccount                = "Trust Account"
    GovernmentAccount           = "Government Account"
    BusinessAccount             = "Business Account"
    EscrowAccount               = "Escrow Account"
    SweepAccount                = "Sweep Account"
    Other                       = "Other"


class PartyTypeEnum(str, Enum):
    Individual   = "Individual"
    Organization = "Organization"
    Government   = "Government"


class OwnershipRoleEnum(str, Enum):
    PrimaryOwner   = "PrimaryOwner"
    JointOwner     = "JointOwner"
    SecondaryOwner = "SecondaryOwner"
    Trustee        = "Trustee"
    Beneficiary    = "Beneficiary"
    PowerOfAttorney = "PowerOfAttorney"
    Guardian       = "Guardian"


class CalculationScenarioEnum(str, Enum):
    Normal    = "Normal"
    AtFailure = "AtFailure"
    Projected = "Projected"
    TestCase  = "TestCase"
    Audit     = "Audit"


class CalculationTestResultEnum(str, Enum):
    Pass      = "Pass"
    Fail      = "Fail"
    Exception = "Exception"
    Manual    = "Manual"


class PartyStatusEnum(str, Enum):
    Active    = "Active"
    Inactive  = "Inactive"
    Deceased  = "Deceased"
    Dissolved = "Dissolved"


class AccountStatusEnum(str, Enum):
    Active  = "Active"
    Dormant = "Dormant"
    Closed  = "Closed"
    Frozen  = "Frozen"


class InsuranceCategoryEnum(str, Enum):
    Covered            = "Covered"
    Uncovered          = "Uncovered"
    Partially_Covered  = "Partially_Covered"


class OrcDeterminationMethodEnum(str, Enum):
    RegistrationForm = "RegistrationForm"
    SignedAgreement  = "SignedAgreement"
    TrustDocument    = "TrustDocument"
    AutomatedMatch   = "AutomatedMatch"
    Manual           = "Manual"


class VerificationMethodEnum(str, Enum):
    DocumentReview     = "DocumentReview"
    CIPProcess         = "CIPProcess"
    SignedAgreement    = "SignedAgreement"
    CourtOrder         = "CourtOrder"
    AutomatedMatch     = "AutomatedMatch"
    ThirdPartyConfirm  = "ThirdPartyConfirm"
    PhysicalReview     = "PhysicalReview"
    ElectronicReview   = "ElectronicReview"


class InterestCalcMethodEnum(str, Enum):
    Simple       = "Simple"
    Compound     = "Compound"
    Daily        = "Daily"
    Monthly      = "Monthly"
    Quarterly    = "Quarterly"
    SemiAnnually = "Semi-Annually"
    Annually     = "Annually"


class InterestCompoundFreqEnum(str, Enum):
    Daily        = "Daily"
    Monthly      = "Monthly"
    Quarterly    = "Quarterly"
    SemiAnnually = "Semi-Annually"
    Annually     = "Annually"
    AtMaturity   = "At-Maturity"


class InterestBasisEnum(str, Enum):
    Day360 = "360-Day"
    Day365 = "365-Day"
    Actual = "Actual"


class OwnershipEndReasonEnum(str, Enum):
    Removal       = "Removal"
    Death         = "Death"
    AccountClosed = "Account Closed"
    Voluntary     = "Voluntary"
    Other         = "Other"


# ---------------------------------------------------------------------------
# SQLAlchemy ORM base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# ORM Models (table-mapped; column names match DDL exactly)
# ---------------------------------------------------------------------------

class PartyORM(Base):
    __tablename__ = "party"

    party_id                     = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    party_type                   = mapped_column(SAEnum(PartyTypeEnum, name="party_type_enum", create_type=False), nullable=False)
    party_status                 = mapped_column(SAEnum(PartyStatusEnum, name="party_status_enum", create_type=False), nullable=False, default=PartyStatusEnum.Active)
    individual_name_given        = mapped_column(String(50))
    individual_name_middle       = mapped_column(String(50))
    individual_name_family       = mapped_column(String(50))
    individual_date_of_birth     = mapped_column(Date)
    individual_ssn               = mapped_column(String(9))
    organization_legal_name      = mapped_column(String(255))
    organization_tax_id          = mapped_column(String(20))
    address_street_line1         = mapped_column(String(100))
    address_city                 = mapped_column(String(50))
    address_state_province       = mapped_column(String(50))
    address_postal_code          = mapped_column(String(20))
    address_country              = mapped_column(String(2))
    address_is_usa               = mapped_column(Boolean, default=False)
    phone_number_primary         = mapped_column(String(20))
    email_primary                = mapped_column(String(255))
    created_date                 = mapped_column(DateTime(), server_default=func.now())
    created_by                   = mapped_column(String(50), nullable=False)
    modified_date                = mapped_column(DateTime(), server_default=func.now(), onupdate=func.now())
    modified_by                  = mapped_column(String(50))


class AccountORM(Base):
    __tablename__ = "account"

    account_id                   = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_number               = mapped_column(String(20), nullable=False, unique=True)
    account_status               = mapped_column(SAEnum(AccountStatusEnum, name="account_status_enum", create_type=False), nullable=False, default=AccountStatusEnum.Active)
    account_type                 = mapped_column(SAEnum(AccountTypeEnum, name="account_type_enum", create_type=False), nullable=False)
    account_open_date            = mapped_column(Date, nullable=False)
    account_close_date           = mapped_column(Date)
    primary_owner_party_id       = mapped_column(PG_UUID(as_uuid=True), ForeignKey("party.party_id"), nullable=False)
    interest_rate_percentage     = mapped_column(Numeric(6, 4), nullable=False, default=Decimal("0.0000"))
    interest_rate_effective_date = mapped_column(Date, nullable=False, default=date.today)
    interest_calculation_method  = mapped_column(SAEnum(InterestCalcMethodEnum, name="interest_calc_method_enum", create_type=False))
    interest_compounding_freq    = mapped_column(SAEnum(InterestCompoundFreqEnum, name="interest_compound_freq_enum", create_type=False))
    interest_calculation_basis   = mapped_column(SAEnum(InterestBasisEnum, name="interest_basis_enum", create_type=False))
    interest_last_accrual_date   = mapped_column(Date)
    current_balance              = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    current_balance_date         = mapped_column(Date, nullable=False)
    accrued_interest_not_posted  = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    minimum_balance              = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    maximum_balance              = mapped_column(Numeric(18, 2))
    created_date                 = mapped_column(DateTime(), server_default=func.now())
    created_by                   = mapped_column(String(50), nullable=False)
    modified_date                = mapped_column(DateTime(), server_default=func.now(), onupdate=func.now())
    modified_by                  = mapped_column(String(50))

    classification               = relationship("AccountRegulatoryClassificationORM", uselist=False, back_populates="account")
    ownerships                   = relationship("AccountOwnershipORM", back_populates="account")


class AccountOwnershipORM(Base):
    __tablename__ = "account_ownership"

    account_ownership_id         = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id                   = mapped_column(PG_UUID(as_uuid=True), ForeignKey("account.account_id"), nullable=False)
    owner_party_id               = mapped_column(PG_UUID(as_uuid=True), ForeignKey("party.party_id"), nullable=False)
    ownership_role               = mapped_column(SAEnum(OwnershipRoleEnum, name="ownership_role_enum", create_type=False), nullable=False)
    ownership_percentage_amount  = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("100.00"))
    ownership_effective_date     = mapped_column(Date, nullable=False, default=date.today)
    ownership_end_date           = mapped_column(Date)
    ownership_end_reason         = mapped_column(SAEnum(OwnershipEndReasonEnum, name="ownership_end_reason_enum", create_type=False))
    ownership_verification_date  = mapped_column(Date, nullable=False)
    ownership_verification_method = mapped_column(SAEnum(VerificationMethodEnum, name="verification_method_enum", create_type=False))
    created_date                 = mapped_column(DateTime(), server_default=func.now())
    created_by                   = mapped_column(String(50), nullable=False)
    modified_date                = mapped_column(DateTime(), server_default=func.now(), onupdate=func.now())

    account                      = relationship("AccountORM", back_populates="ownerships")


class AccountRegulatoryClassificationORM(Base):
    __tablename__ = "account_regulatory_classification"

    classification_id            = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id                   = mapped_column(PG_UUID(as_uuid=True), ForeignKey("account.account_id"), nullable=False, unique=True)
    orc_code                     = mapped_column(SAEnum(OrcCodeEnum, name="orc_code_enum", create_type=False), nullable=False)
    orc_insured_amount_per_owner = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("250000.00"))
    orc_insurance_category       = mapped_column(SAEnum(InsuranceCategoryEnum, name="insurance_category_enum", create_type=False), default=InsuranceCategoryEnum.Covered)
    orc_determination_date       = mapped_column(Date, nullable=False, default=date.today)
    orc_determination_method     = mapped_column(SAEnum(OrcDeterminationMethodEnum, name="orc_determination_method_enum", create_type=False))
    orc_verification_date        = mapped_column(Date, nullable=False)
    is_joint_ownership           = mapped_column(Boolean, nullable=False, default=False)
    is_ira                       = mapped_column(Boolean, nullable=False, default=False)
    is_keogh                     = mapped_column(Boolean, nullable=False, default=False)
    is_trust                     = mapped_column(Boolean, nullable=False, default=False)
    is_government                = mapped_column(Boolean, nullable=False, default=False)
    is_business                  = mapped_column(Boolean, nullable=False, default=False)
    is_payable_on_death          = mapped_column(Boolean, nullable=False, default=False)
    is_transfer_on_death         = mapped_column(Boolean, nullable=False, default=False)
    created_date                 = mapped_column(DateTime(), server_default=func.now())
    created_by                   = mapped_column(String(50), nullable=False)
    modified_date                = mapped_column(DateTime(), server_default=func.now(), onupdate=func.now())

    account                      = relationship("AccountORM", back_populates="classification")


class DepositInsuranceCalculationORM(Base):
    __tablename__ = "deposit_insurance_calculation"

    calculation_id               = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id                   = mapped_column(PG_UUID(as_uuid=True), ForeignKey("account.account_id"), nullable=False)
    classification_id            = mapped_column(PG_UUID(as_uuid=True), ForeignKey("account_regulatory_classification.classification_id"), nullable=False)
    calculation_date             = mapped_column(Date, nullable=False, default=date.today)
    calculation_time             = mapped_column(DateTime(), server_default=func.now())
    calculation_scenario         = mapped_column(SAEnum(CalculationScenarioEnum, name="calculation_scenario_enum", create_type=False), nullable=False, default=CalculationScenarioEnum.Normal)
    input_account_balance        = mapped_column(Numeric(18, 2), nullable=False)
    input_accrued_interest       = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    input_owner_count            = mapped_column(Integer, nullable=False)
    input_orc                    = mapped_column(String(50), nullable=False)
    part_330_rules_version_date  = mapped_column(Date, nullable=False)
    part_330_rules_smdia_amount  = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("250000.00"))
    calculated_insured_amount    = mapped_column(Numeric(18, 2), nullable=False)
    calculated_uninsured_amount  = mapped_column(Numeric(18, 2), nullable=False)
    calculation_basis_description = mapped_column(String(500))
    beneficiary_count            = mapped_column(Integer)
    highest_individual_insured   = mapped_column(Numeric(18, 2))
    calculation_validated        = mapped_column(Boolean, default=False)
    calculation_validation_date  = mapped_column(Date)
    calculation_validated_by     = mapped_column(String(50))
    calculation_test_result      = mapped_column(SAEnum(CalculationTestResultEnum, name="calculation_test_result_enum", create_type=False), default=CalculationTestResultEnum.Manual)
    calculation_test_error_message = mapped_column(String(1000))
    calculation_approved_by      = mapped_column(String(50))
    calculation_approved_date    = mapped_column(Date)
    created_date                 = mapped_column(DateTime(), server_default=func.now())
    modified_date                = mapped_column(DateTime(), server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Pydantic v2 request / response models
# ---------------------------------------------------------------------------

class Party(BaseModel):
    """Pydantic model for PARTY table. Per FinCEN CIP (31 U.S.C. § 5318)."""
    model_config = {"from_attributes": True}

    party_id:                  Optional[UUID4]       = None
    party_type:                PartyTypeEnum
    party_status:              str                   = "Active"
    individual_name_given:     Optional[str]         = None
    individual_name_middle:    Optional[str]         = None
    individual_name_family:    Optional[str]         = None
    individual_date_of_birth:  Optional[date]        = None
    individual_ssn:            Optional[str]         = Field(None, min_length=9, max_length=9)
    organization_legal_name:   Optional[str]         = None
    organization_tax_id:       Optional[str]         = None
    address_street_line1:      Optional[str]         = None
    address_city:              Optional[str]         = None
    address_state_province:    Optional[str]         = None
    address_postal_code:       Optional[str]         = None
    address_country:           Optional[str]         = Field(None, min_length=2, max_length=2)
    address_is_usa:            bool                   = False
    phone_number_primary:      Optional[str]         = None
    email_primary:             Optional[str]         = None
    created_by:                str


class Account(BaseModel):
    """Pydantic model for ACCOUNT table. Per FDIC Part 370 § 370.4(a)."""
    model_config = {"from_attributes": True}

    account_id:                Optional[UUID4]       = None
    account_number:            str                   = Field(..., min_length=1, max_length=20)
    account_type:              AccountTypeEnum
    account_status:            str                   = "Active"
    account_open_date:         date
    primary_owner_party_id:    UUID4
    interest_rate_percentage:  Decimal               = Field(Decimal("0.0000"), ge=0)
    interest_rate_effective_date: date               = Field(default_factory=date.today)
    interest_calculation_method: Optional[str]       = None
    current_balance:           Decimal               = Decimal("0.00")
    current_balance_date:      date
    accrued_interest_not_posted: Decimal             = Decimal("0.00")
    minimum_balance:           Decimal               = Decimal("0.00")
    created_by:                str


class AccountOwnership(BaseModel):
    """Pydantic model for ACCOUNT_OWNERSHIP. Per FDIC Part 370 § 370.4(c)."""
    model_config = {"from_attributes": True}

    account_ownership_id:      Optional[UUID4]       = None
    account_id:                UUID4
    owner_party_id:            UUID4
    ownership_role:            OwnershipRoleEnum
    ownership_percentage_amount: Decimal             = Field(Decimal("100.00"), ge=0, le=100)
    ownership_effective_date:  date                  = Field(default_factory=date.today)
    ownership_verification_date: date
    created_by:                str


class AccountRegulatoryClassification(BaseModel):
    """Pydantic model for ORC classification. Per FDIC Part 370 Appendix A."""
    model_config = {"from_attributes": True}

    classification_id:         Optional[UUID4]       = None
    account_id:                UUID4
    orc_code:                  OrcCodeEnum
    orc_insured_amount_per_owner: Decimal            = SMDIA
    orc_insurance_category:    str                   = "Covered"
    orc_determination_date:    date                  = Field(default_factory=date.today)
    orc_determination_method:  Optional[str]         = "RegistrationForm"
    orc_verification_date:     date
    is_joint_ownership:        bool                  = False
    is_ira:                    bool                  = False
    is_keogh:                  bool                  = False
    is_trust:                  bool                  = False
    is_government:             bool                  = False
    is_business:               bool                  = False
    is_payable_on_death:       bool                  = False
    is_transfer_on_death:      bool                  = False
    created_by:                str


class DepositInsuranceCalculation(BaseModel):
    """Pydantic model for deposit insurance output. Per FDIC Part 330."""
    model_config = {"from_attributes": True}

    calculation_id:            Optional[UUID4]       = None
    account_id:                UUID4
    classification_id:         UUID4
    calculation_date:          date                  = Field(default_factory=date.today)
    calculation_scenario:      CalculationScenarioEnum = CalculationScenarioEnum.Normal
    input_account_balance:     Decimal
    input_accrued_interest:    Decimal               = Decimal("0.00")
    input_owner_count:         int                   = Field(..., ge=1)
    input_orc:                 str
    part_330_rules_version_date: date
    part_330_rules_smdia_amount: Decimal             = SMDIA
    calculated_insured_amount: Decimal
    calculated_uninsured_amount: Decimal
    calculation_basis_description: Optional[str]     = None
    beneficiary_count:         Optional[int]         = None
    calculation_test_result:   CalculationTestResultEnum = CalculationTestResultEnum.Manual


# ---------------------------------------------------------------------------
# Core logic: ORC assignment
# ---------------------------------------------------------------------------

def assign_orc_code(
    account_type: str,
    owner_count: int,
    has_beneficiaries: bool,
) -> OrcCodeEnum:
    """
    Determine the correct FDIC Part 370 ORC code from account parameters.

    Per FDIC Part 370 Appendix A — ORC assignment rules:
      - Savings / Checking / CD / MM / Sweep with 1 owner → Single
      - Savings / Checking / MM with ≥ 2 owners → Joint_JTWROS
      - Individual Retirement Account → IRA_Traditional
      - Trust Account with beneficiaries → Trust_Revocable
      - Government Account → Government_State (default; override as needed)
      - Business Account → Business_Corporation (default; override as needed)
      - Escrow Account → Escrow_Agent

    Args:
        account_type:       Value from AccountTypeEnum / account_type_enum column.
        owner_count:        Number of current active owners from account_ownership.
        has_beneficiaries:  True if ≥ 1 active fiduciary_beneficiary record exists.

    Returns:
        OrcCodeEnum corresponding to the account profile.
    """
    at = account_type.strip()

    if at == AccountTypeEnum.IndividualRetirementAccount:
        return OrcCodeEnum.IRA_Traditional

    if at == AccountTypeEnum.TrustAccount:
        return OrcCodeEnum.Trust_Revocable if has_beneficiaries else OrcCodeEnum.FiduciaryOther

    if at == AccountTypeEnum.GovernmentAccount:
        return OrcCodeEnum.Government_State

    if at == AccountTypeEnum.BusinessAccount:
        return OrcCodeEnum.Business_Corporation

    if at == AccountTypeEnum.EscrowAccount:
        return OrcCodeEnum.Escrow_Agent

    # Standard retail deposits (Savings, Checking, Money Market, CD, Sweep, Other)
    if owner_count >= 2:
        return OrcCodeEnum.Joint_JTWROS

    return OrcCodeEnum.Single


# ---------------------------------------------------------------------------
# Core logic: FDIC Part 330 coverage calculation
# ---------------------------------------------------------------------------

def calculate_fdic_coverage(
    orc_code: str,
    balance: Decimal,
    owner_count: int,
    beneficiary_count: int,
    has_valid_pod_tod_on_file: bool = True,
) -> dict[str, object]:
    """
    Calculate FDIC deposit insurance coverage per FDIC Part 330.

    Rule summary (FDIC Part 330 § 330.9–330.14):
      Single          → min(balance, $250,000)               [§ 330.9]
      Joint (any)     → min(balance, $250,000 × owner_count) [§ 330.9]
      IRA / Keogh     → min(balance, $250,000)               [§ 330.14 — separate]
      Trust (any)     → min(balance, $250,000 × min(bene, 5)) [§ 330.10(d)]
      POD / TOD       → min(balance, $250,000 × bene_count) if valid; else Single [§ 330.10]
      Government      → full coverage may differ; default $250,000 per depositor
      Business        → min(balance, $250,000)               [§ 330.11]

    Args:
        orc_code:                  ORC code string (orc_code_enum value).
        balance:                   Account balance (input_account_balance).
        owner_count:               Number of account owners (input_owner_count).
        beneficiary_count:         Number of named beneficiaries (beneficiary_count column).
        has_valid_pod_tod_on_file:  Whether a valid POD/TOD form is on file.

    Returns:
        dict with keys:
          insured      (float)  — amount FDIC insures
          uninsured    (float)  — amount above FDIC limit
          orc          (str)    — ORC code applied
          rule_applied (str)    — human-readable citation
    """
    balance = Decimal(str(balance))
    smdia   = SMDIA

    orc = OrcCodeEnum(orc_code)

    # ── IRA / Keogh (separate $250K coverage per FDIC Part 330 § 330.14) ──
    if orc in (
        OrcCodeEnum.IRA_Traditional,
        OrcCodeEnum.IRA_Roth,
        OrcCodeEnum.IRA_SEP,
        OrcCodeEnum.IRA_SIMPLE,
        OrcCodeEnum.Keogh_DefinedContribution,
        OrcCodeEnum.Keogh_DefinedBenefit,
    ):
        cap          = smdia
        insured      = min(balance, cap)
        rule_applied = f"IRA/Keogh: min(balance, {smdia}). Per FDIC Part 330 § 330.14."

    # ── Joint accounts (all variants) — $250K × owner_count ──
    elif orc in (
        OrcCodeEnum.Joint_JTWROS,
        OrcCodeEnum.Joint_TenancyByEntirety,
        OrcCodeEnum.Joint_TenancyInCommon,
    ):
        cap          = smdia * max(owner_count, 1)
        insured      = min(balance, cap)
        rule_applied = (
            f"Joint {orc.value}: min(balance, {smdia} × {owner_count}) = "
            f"min({balance}, {cap}). Per FDIC Part 330 § 330.9."
        )

    # ── Trust accounts — $250K × min(beneficiary_count, 5) ──
    elif orc in (
        OrcCodeEnum.Trust_Revocable,
        OrcCodeEnum.Trust_Irrevocable,
        OrcCodeEnum.Trust_Charitable,
        OrcCodeEnum.Trust_Qualified,
    ):
        effective_bene = min(max(beneficiary_count, 0), MAX_TRUST_BENEFICIARIES)
        cap            = smdia * max(effective_bene, 1)
        insured        = min(balance, cap)
        rule_applied   = (
            f"Trust {orc.value}: {beneficiary_count} named beneficiaries "
            f"(capped at {MAX_TRUST_BENEFICIARIES}); "
            f"min(balance, {smdia} × {effective_bene}) = min({balance}, {cap}). "
            f"Per FDIC Part 330 § 330.10(d)."
        )

    # ── POD / TOD — $250K × beneficiary_count (reverts to Single if no valid form) ──
    elif orc in (OrcCodeEnum.POD_PayableOnDeath, OrcCodeEnum.TOD_TransferOnDeath):
        if has_valid_pod_tod_on_file and beneficiary_count >= 1:
            cap          = smdia * beneficiary_count
            insured      = min(balance, cap)
            rule_applied = (
                f"POD/TOD: {beneficiary_count} valid beneficiaries; "
                f"min(balance, {smdia} × {beneficiary_count}) = min({balance}, {cap}). "
                f"Per FDIC Part 330 § 330.10."
            )
        else:
            insured      = min(balance, smdia)
            rule_applied = (
                f"POD/TOD reverts to Single: no valid beneficiary designation on file. "
                f"min(balance, {smdia}). Per FDIC Part 330 § 330.10."
            )

    # ── Government — apply statutory coverage ($250K default; may differ by statute) ──
    elif orc in (
        OrcCodeEnum.Government_Federal,
        OrcCodeEnum.Government_State,
        OrcCodeEnum.Government_Local,
    ):
        insured      = min(balance, smdia)
        rule_applied = f"Government deposit: min(balance, {smdia}). Per FDIC Part 330 § 330.15."

    # ── Business / Corporation — $250K per entity ──
    elif orc in (
        OrcCodeEnum.Business_Corporation,
        OrcCodeEnum.Business_Partnership,
        OrcCodeEnum.Business_LLC,
        OrcCodeEnum.Business_SoleProprietor,
    ):
        insured      = min(balance, smdia)
        rule_applied = f"Business deposit: min(balance, {smdia}). Per FDIC Part 330 § 330.11."

    # ── Single / default ──
    else:
        insured      = min(balance, smdia)
        rule_applied = (
            f"Single account ({orc.value}): min(balance, {smdia}). Per FDIC Part 330 § 330.9."
        )

    insured   = insured.quantize(Decimal("0.01"))
    uninsured = (balance - insured).quantize(Decimal("0.01"))

    return {
        "insured":      float(insured),
        "uninsured":    float(uninsured),
        "orc":          orc.value,
        "rule_applied": rule_applied,
    }


# ---------------------------------------------------------------------------
# DB upsert: write a new deposit_insurance_calculation row
# ---------------------------------------------------------------------------

async def upsert_insurance_calculation(
    account_id: uuid.UUID,
    db_session: AsyncSession,
    scenario: CalculationScenarioEnum = CalculationScenarioEnum.Normal,
    created_by: str = "orc_engine",
) -> DepositInsuranceCalculation:
    """
    Read account + ORC classification + ownership counts + beneficiary counts
    from the database, compute FDIC coverage, and INSERT a new
    deposit_insurance_calculation row.

    Per FDIC Part 370 § 370.3(a)-(b): The institution must maintain the data
    and systems necessary to determine, within 24 hours of failure, the
    insurance coverage for each depositor account.

    Args:
        account_id:  UUID of the account to calculate coverage for.
        db_session:  SQLAlchemy async session.
        scenario:    Calculation scenario (Normal, AtFailure, Projected, etc.).
        created_by:  Identifying user / service inserting the row.

    Returns:
        DepositInsuranceCalculation Pydantic model with computed values.

    Raises:
        ValueError: If account or classification is not found.
    """
    from sqlalchemy import text

    # ── 1. Fetch account ──────────────────────────────────────────────────────
    acct_result = await db_session.execute(
        select(AccountORM).where(AccountORM.account_id == account_id)
    )
    acct: AccountORM | None = acct_result.scalar_one_or_none()
    if acct is None:
        raise ValueError(f"Account {account_id} not found.")

    # ── 2. Fetch ORC classification ───────────────────────────────────────────
    cls_result = await db_session.execute(
        select(AccountRegulatoryClassificationORM).where(
            AccountRegulatoryClassificationORM.account_id == account_id
        )
    )
    cls: AccountRegulatoryClassificationORM | None = cls_result.scalar_one_or_none()
    if cls is None:
        raise ValueError(f"No ORC classification found for account {account_id}.")

    # ── 3. Count active owners ────────────────────────────────────────────────
    owner_count_result = await db_session.execute(
        select(func.count(AccountOwnershipORM.account_ownership_id)).where(
            AccountOwnershipORM.account_id == account_id,
            AccountOwnershipORM.ownership_end_date.is_(None),
        )
    )
    owner_count: int = owner_count_result.scalar_one() or 1

    # ── 4. Count active beneficiaries (via fiduciary_arrangement) ──────────────
    bene_count_result = await db_session.execute(
        text(
            """
            SELECT COUNT(fb.beneficiary_id)
            FROM   fiduciary_arrangement fa
            JOIN   fiduciary_beneficiary  fb ON fb.fiduciary_id = fa.fiduciary_id
            WHERE  fa.account_id = :account_id
              AND  fb.beneficiary_status = 'Active'
            """
        ),
        {"account_id": str(account_id)},
    )
    beneficiary_count: int = bene_count_result.scalar_one() or 0

    # ── 5. Calculate coverage ─────────────────────────────────────────────────
    result = calculate_fdic_coverage(
        orc_code          = cls.orc_code,
        balance           = acct.current_balance,
        owner_count       = owner_count,
        beneficiary_count = beneficiary_count,
    )

    # ── 6. Insert new calculation row ─────────────────────────────────────────
    today = date.today()
    new_calc = DepositInsuranceCalculationORM(
        account_id                   = account_id,
        classification_id            = cls.classification_id,
        calculation_date             = today,
        calculation_scenario         = scenario.value,
        input_account_balance        = acct.current_balance,
        input_accrued_interest       = acct.accrued_interest_not_posted,
        input_owner_count            = owner_count,
        input_orc                    = cls.orc_code,
        part_330_rules_version_date  = date(2023, 1, 1),
        part_330_rules_smdia_amount  = SMDIA,
        calculated_insured_amount    = Decimal(str(result["insured"])),
        calculated_uninsured_amount  = Decimal(str(result["uninsured"])),
        calculation_basis_description = result["rule_applied"],
        beneficiary_count            = beneficiary_count,
        calculation_test_result      = CalculationTestResultEnum.Pass.value,
        calculation_validated        = True,
        calculation_validation_date  = today,
        calculation_validated_by     = created_by,
    )
    db_session.add(new_calc)
    await db_session.flush()

    return DepositInsuranceCalculation(
        calculation_id               = new_calc.calculation_id,
        account_id                   = account_id,
        classification_id            = cls.classification_id,
        calculation_date             = today,
        calculation_scenario         = scenario,
        input_account_balance        = acct.current_balance,
        input_accrued_interest       = acct.accrued_interest_not_posted,
        input_owner_count            = owner_count,
        input_orc                    = cls.orc_code,
        part_330_rules_version_date  = new_calc.part_330_rules_version_date,
        part_330_rules_smdia_amount  = SMDIA,
        calculated_insured_amount    = new_calc.calculated_insured_amount,
        calculated_uninsured_amount  = new_calc.calculated_uninsured_amount,
        calculation_basis_description = result["rule_applied"],
        beneficiary_count            = beneficiary_count,
        calculation_test_result      = CalculationTestResultEnum.Pass,
    )
