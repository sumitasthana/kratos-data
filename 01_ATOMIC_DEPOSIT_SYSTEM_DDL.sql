-- ============================================================================
-- ATOMIC DEPOSIT SYSTEM DATA MODEL (FDIC PART 370 COMPLIANT)
-- PostgreSQL DDL Script
-- ============================================================================
-- Purpose: Create highly normalized, atomic data structures for retail bank
--          deposit accounts with full Part 370 (Recordkeeping for Timely
--          Deposit Insurance Determination) compliance.
--
-- Principles:
--   - Each column = single, irreducible fact
--   - No composite columns; decomposed to maximum atomicity
--   - Features/derived attributes built via views (not stored)
--   - Full audit trail (created_date, created_by, modified_date)
--   - Regulatory traceability (Part 370, Part 330 references)
--
-- Author: Risk & Controls Expert
-- Version: 1.0
-- Created: 2026-02-02
-- ============================================================================

-- ============================================================================
-- SECTION 1: ENUMS (DOMAIN TYPES)
-- ============================================================================

-- Party Type Enumeration
CREATE TYPE party_type_enum AS ENUM (
  'Individual',
  'Organization',
  'Government'
);

-- Party Status Enumeration
CREATE TYPE party_status_enum AS ENUM (
  'Active',
  'Inactive',
  'Deceased',
  'Dissolved'
);

-- Gender Enumeration
CREATE TYPE gender_enum AS ENUM (
  'M',
  'F',
  'Other',
  'Declined'
);

-- Organization Type Enumeration
CREATE TYPE organization_type_enum AS ENUM (
  'Corporation',
  'Partnership',
  'LLC',
  'Government',
  'Trust',
  'Other'
);

-- Government Entity Type Enumeration
CREATE TYPE government_type_enum AS ENUM (
  'Federal',
  'State',
  'Local',
  'Other'
);

-- Account Status Enumeration
CREATE TYPE account_status_enum AS ENUM (
  'Active',
  'Dormant',
  'Closed',
  'Frozen'
);

-- Account Type Enumeration (product types)
CREATE TYPE account_type_enum AS ENUM (
  'Savings',
  'Checking',
  'Money Market',
  'Certificate of Deposit',
  'Individual Retirement Account',
  'Trust Account',
  'Government Account',
  'Business Account',
  'Escrow Account',
  'Sweep Account',
  'Other'
);

-- Interest Calculation Method Enumeration
CREATE TYPE interest_calc_method_enum AS ENUM (
  'Simple',
  'Compound',
  'Daily',
  'Monthly',
  'Quarterly',
  'Semi-Annually',
  'Annually'
);

-- Interest Compounding Frequency Enumeration
CREATE TYPE interest_compound_freq_enum AS ENUM (
  'Daily',
  'Monthly',
  'Quarterly',
  'Semi-Annually',
  'Annually',
  'At-Maturity'
);

-- Interest Calculation Basis Enumeration (day count convention)
CREATE TYPE interest_basis_enum AS ENUM (
  '360-Day',
  '365-Day',
  'Actual'
);

-- Ownership Right & Capacity (ORC) Code Enumeration - Per FDIC Part 370 Appendix A
CREATE TYPE orc_code_enum AS ENUM (
  'Single',
  'Joint_TenancyByEntirety',
  'Joint_TenancyInCommon',
  'Joint_JTWROS',
  'IRA_Traditional',
  'IRA_Roth',
  'IRA_SEP',
  'IRA_SIMPLE',
  'Keogh_DefinedContribution',
  'Keogh_DefinedBenefit',
  'Trust_Revocable',
  'Trust_Irrevocable',
  'Trust_Charitable',
  'Trust_Qualified',
  'Escrow_Agent',
  'Government_Federal',
  'Government_State',
  'Government_Local',
  'Business_Corporation',
  'Business_Partnership',
  'Business_LLC',
  'Business_SoleProprietor',
  'POD_PayableOnDeath',
  'TOD_TransferOnDeath',
  'FiduciaryOther'
);

-- Insurance Category Enumeration
CREATE TYPE insurance_category_enum AS ENUM (
  'Covered',
  'Uncovered',
  'Partially_Covered'
);

-- Ownership Role Enumeration
CREATE TYPE ownership_role_enum AS ENUM (
  'PrimaryOwner',
  'JointOwner',
  'SecondaryOwner',
  'Trustee',
  'Beneficiary',
  'PowerOfAttorney',
  'Guardian'
);

-- Ownership End Reason Enumeration
CREATE TYPE ownership_end_reason_enum AS ENUM (
  'Removal',
  'Death',
  'Account Closed',
  'Voluntary',
  'Other'
);

-- Verification Method Enumeration
CREATE TYPE verification_method_enum AS ENUM (
  'DocumentReview',
  'CIPProcess',
  'SignedAgreement',
  'CourtOrder',
  'AutomatedMatch',
  'ThirdPartyConfirm',
  'PhysicalReview',
  'ElectronicReview'
);

-- ORC Determination Method Enumeration
CREATE TYPE orc_determination_method_enum AS ENUM (
  'RegistrationForm',
  'SignedAgreement',
  'TrustDocument',
  'AutomatedMatch',
  'Manual'
);

-- Fiduciary Type Enumeration
CREATE TYPE fiduciary_type_enum AS ENUM (
  'Trust_Revocable',
  'Trust_Irrevocable',
  'Trust_Charitable',
  'Trust_QualifiedPersonalResidence',
  'Trust_QualifiedDomesticTrust',
  'Escrow_RealEstate',
  'Escrow_Legal',
  'Escrow_Court',
  'Agency_PowerOfAttorney',
  'Agency_Guardianship',
  'Agency_Conservatorship',
  'Custodial_UTMA',
  'Custodial_UGMA',
  'Other'
);

-- Beneficiary Type Enumeration
CREATE TYPE beneficiary_type_enum AS ENUM (
  'Individual',
  'Organization',
  'Class_ChildrenOfSettlor',
  'Class_DescendantsOfSettlor',
  'Class_Spouse',
  'Class_Grandchildren',
  'Charity',
  'Estate',
  'Other'
);

-- Beneficiary Status Enumeration
CREATE TYPE beneficiary_status_enum AS ENUM (
  'Active',
  'Deceased',
  'Disclaimed',
  'Removed'
);

-- Distribution Condition Enumeration
CREATE TYPE distribution_condition_enum AS ENUM (
  'Immediate',
  'Upon Age Attainment',
  'Contingent',
  'At Trustee Discretion',
  'Other'
);

-- Designation Method Enumeration
CREATE TYPE designation_method_enum AS ENUM (
  'TrustDocument',
  'Amendment',
  'CourtOrder'
);

-- Account Feature Type Enumeration
CREATE TYPE account_feature_type_enum AS ENUM (
  'Sweep_ToAccount',
  'Sweep_FromAccount',
  'Sweep_Bi-directional',
  'POD_PayableOnDeath',
  'TOD_TransferOnDeath',
  'ZeroBalance',
  'AutomaticTransfer',
  'OverdraftProtection',
  'AccountLinkage',
  'MoneyMarketSweep',
  'LiquidityReserve',
  'CourtEscrow',
  'TaxWithholding',
  'Other'
);

-- Feature Status Enumeration
CREATE TYPE feature_status_enum AS ENUM (
  'Active',
  'Inactive',
  'Suspended',
  'Terminated'
);

-- Sweep Trigger Type Enumeration
CREATE TYPE sweep_trigger_type_enum AS ENUM (
  'IfBelowAmount',
  'IfAboveAmount',
  'IfExceeds'
);

-- Sweep Frequency Enumeration
CREATE TYPE sweep_frequency_enum AS ENUM (
  'Daily',
  'Weekly',
  'Monthly',
  'AsNeeded',
  'RealTime'
);

-- Sweep Direction Enumeration
CREATE TYPE sweep_direction_enum AS ENUM (
  'ToLinkedAccount',
  'FromLinkedAccount'
);

-- Transaction Type Enumeration
CREATE TYPE transaction_type_enum AS ENUM (
  'Deposit_Cash',
  'Deposit_Check',
  'Deposit_ACH',
  'Deposit_Wire',
  'Deposit_Transfer',
  'Deposit_Interest',
  'Withdrawal_ATM',
  'Withdrawal_Check',
  'Withdrawal_ACH',
  'Withdrawal_Wire',
  'Withdrawal_Transfer',
  'Withdrawal_Fee',
  'Withdrawal_Overdraft',
  'Correction_Debit',
  'Correction_Credit',
  'Reversal',
  'Sweep',
  'Other'
);

-- Transaction Status Enumeration
CREATE TYPE transaction_status_enum AS ENUM (
  'Pending',
  'Posted',
  'Settled',
  'Cancelled',
  'Reversed',
  'Failed'
);

-- GL Reconciliation Status Enumeration
CREATE TYPE gl_reconciliation_status_enum AS ENUM (
  'Reconciled',
  'Pending',
  'Exception',
  'ManualOverride'
);

-- Calculation Scenario Enumeration
CREATE TYPE calculation_scenario_enum AS ENUM (
  'Normal',
  'AtFailure',
  'Projected',
  'TestCase',
  'Audit'
);

-- Calculation Test Result Enumeration
CREATE TYPE calculation_test_result_enum AS ENUM (
  'Pass',
  'Fail',
  'Exception',
  'Manual'
);

-- Verification Status Enumeration
CREATE TYPE verification_status_enum AS ENUM (
  'Complete',
  'Pending',
  'Failed',
  'Exception',
  'Manual_Review'
);

-- Risk Rating Enumeration
CREATE TYPE risk_rating_enum AS ENUM (
  'Low',
  'Medium',
  'High',
  'Critical'
);

-- Sanctions Screening Result Enumeration
CREATE TYPE sanctions_result_enum AS ENUM (
  'Clear',
  'Match',
  'PossibleMatch',
  'Manual_Review'
);

-- PEP Status Enumeration
CREATE TYPE pep_status_enum AS ENUM (
  'NotPEP',
  'PEP',
  'FamilyOfPEP',
  'CloseAssociate',
  'Unknown'
);

-- CIP Verification Method Enumeration
CREATE TYPE cip_verification_method_enum AS ENUM (
  'DocumentReview_DriversLicense',
  'DocumentReview_Passport',
  'DocumentReview_GovernmentID',
  'DocumentReview_Military',
  'DocumentReview_StateID',
  'BiometricMatch_FacialRecognition',
  'BiometricMatch_Fingerprint',
  'ThirdPartyMatch_Equifax',
  'ThirdPartyMatch_Experian',
  'ThirdPartyMatch_TransUnion',
  'DocumentaryMethod',
  'NonDocumentaryMethod',
  'Manual_Review',
  'Other'
);

-- Verification Program Type Enumeration
CREATE TYPE verification_program_type_enum AS ENUM (
  'CIP',
  'KYC',
  'KYCC',
  'Enhanced',
  'Simplified'
);

-- Address Verification Method Enumeration
CREATE TYPE address_verification_method_enum AS ENUM (
  'DocumentReview',
  'ThirdParty',
  'UtilityBill',
  'GovernmentDocument',
  'Notarized'
);

-- Sanctions Database Enumeration
CREATE TYPE sanctions_database_enum AS ENUM (
  'OFAC',
  'FinCEN',
  'EU',
  'UN',
  'Other'
);

-- ============================================================================
-- SECTION 2: BASE TABLES (ATOMIC ENTITIES)
-- ============================================================================

-- TABLE: PARTY (Most Atomic: Individual or Organization)
-- Purpose: Single source of truth for all parties (customers, organizations, etc.)
-- Regulatory: Required for identity verification (CIP/KYC per FinCEN)
CREATE TABLE party (
  party_id                     UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Party Type (discriminates which columns apply)
  party_type                   party_type_enum NOT NULL,
  
  -- INDIVIDUAL ATTRIBUTES
  individual_name_given        VARCHAR(50),
  individual_name_middle       VARCHAR(50),
  individual_name_family       VARCHAR(50),
  individual_name_suffix       VARCHAR(20),
  individual_date_of_birth     DATE,
  individual_ssn               CHAR(9),        -- Stored without dashes; e.g., "123456789"
  individual_country_of_birth  CHAR(2),        -- ISO 3166-1 alpha-2
  individual_gender            gender_enum,
  
  -- ORGANIZATION ATTRIBUTES
  organization_legal_name      VARCHAR(255),
  organization_tax_id          VARCHAR(20),    -- EIN format: XX-XXXXXXX
  organization_type            organization_type_enum,
  organization_country_of_inc  CHAR(2),
  organization_state_of_inc    CHAR(2),
  
  -- GOVERNMENT ATTRIBUTES
  government_entity_name       VARCHAR(255),
  government_entity_type       government_type_enum,
  government_jurisdiction      VARCHAR(100),
  
  -- CONTACT INFORMATION
  phone_number_primary         VARCHAR(20),    -- +1-XXX-XXX-XXXX format
  phone_number_alternate       VARCHAR(20),
  email_primary                VARCHAR(255),
  email_alternate              VARCHAR(255),
  
  -- ADDRESS (PRIMARY)
  address_street_line1         VARCHAR(100),
  address_street_line2         VARCHAR(100),
  address_city                 VARCHAR(50),
  address_state_province       VARCHAR(50),
  address_postal_code          VARCHAR(20),
  address_country              CHAR(2),        -- ISO 3166-1 alpha-2
  address_is_usa               BOOLEAN         DEFAULT FALSE,
  
  -- LIFECYCLE
  party_status                 party_status_enum NOT NULL DEFAULT 'Active',
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_by                  VARCHAR(50),
  
  -- CONSTRAINTS
  CHECK (party_type IN ('Individual', 'Organization', 'Government'))
);

CREATE INDEX idx_party_type ON party(party_type);
CREATE INDEX idx_party_status ON party(party_status);
CREATE INDEX idx_party_created_date ON party(created_date);
CREATE INDEX idx_individual_ssn ON party(individual_ssn) WHERE individual_ssn IS NOT NULL;
CREATE INDEX idx_organization_tax_id ON party(organization_tax_id) WHERE organization_tax_id IS NOT NULL;

-- Partial unique indexes (PostgreSQL partial indexes replace inline UNIQUE...WHERE)
CREATE UNIQUE INDEX ux_party_individual_ssn
  ON party (individual_ssn)
  WHERE individual_ssn IS NOT NULL;

CREATE UNIQUE INDEX ux_party_organization_tax_id
  ON party (organization_tax_id)
  WHERE organization_tax_id IS NOT NULL;

-- TABLE: ACCOUNT (Most Atomic: Deposit Account)
-- Purpose: Core deposit account records; one per customer per product
-- Regulatory: Per FDIC Part 370 § 370.4 - Account details
CREATE TABLE account (
  account_id                   UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- ACCOUNT IDENTIFIERS
  account_number               VARCHAR(20)     NOT NULL UNIQUE,
  account_status               account_status_enum NOT NULL DEFAULT 'Active',
  account_type                 account_type_enum NOT NULL,
  
  -- DATES
  account_open_date            DATE            NOT NULL,
  account_close_date           DATE,
  
  -- OWNER REFERENCE
  primary_owner_party_id       UUID            NOT NULL REFERENCES party(party_id),
  
  -- INTEREST ATTRIBUTES
  interest_rate_percentage     NUMERIC(6, 4)   NOT NULL DEFAULT 0.0000,  -- e.g., 1.2500
  interest_rate_effective_date DATE            NOT NULL DEFAULT CURRENT_DATE,
  interest_rate_expiry_date    DATE,
  interest_calculation_method  interest_calc_method_enum,
  interest_compounding_freq    interest_compound_freq_enum,
  interest_calculation_basis   interest_basis_enum,
  interest_last_accrual_date   DATE,
  
  -- BALANCE TRACKING
  current_balance              NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  current_balance_date         DATE            NOT NULL,
  accrued_interest_not_posted  NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  
  -- LIMITS & RESTRICTIONS
  minimum_balance              NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  maximum_balance              NUMERIC(18, 2),
  transaction_daily_withdrawal_limit NUMERIC(18, 2),
  transaction_monthly_withdrawal_limit INT,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_by                  VARCHAR(50)
);

CREATE INDEX idx_account_status ON account(account_status);
CREATE INDEX idx_account_primary_owner ON account(primary_owner_party_id);
CREATE INDEX idx_account_open_date ON account(account_open_date);
CREATE INDEX idx_account_current_balance_date ON account(current_balance_date);
CREATE INDEX idx_account_number ON account(account_number);

-- TABLE: ACCOUNT_OWNERSHIP (Most Atomic: Links ACCOUNT to Multiple PARTY owners)
-- Purpose: Captures joint, multi-owner, and succession scenarios
-- Regulatory: Required for Part 370 § 370.4(c) - Ownership Right & Capacity
CREATE TABLE account_ownership (
  account_ownership_id         UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEYS
  account_id                   UUID            NOT NULL REFERENCES account(account_id),
  owner_party_id               UUID            NOT NULL REFERENCES party(party_id),
  
  -- OWNERSHIP DETAILS
  ownership_role               ownership_role_enum NOT NULL,
  ownership_percentage_amount  NUMERIC(5, 2)   NOT NULL DEFAULT 100.00,
  
  -- LIFECYCLE
  ownership_effective_date     DATE            NOT NULL DEFAULT CURRENT_DATE,
  ownership_end_date           DATE,
  ownership_end_reason         ownership_end_reason_enum,
  
  -- VERIFICATION
  ownership_verification_date  DATE            NOT NULL,
  ownership_verification_method verification_method_enum,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- CONSTRAINTS
  UNIQUE (account_id, owner_party_id),
  CONSTRAINT ck_ownership_percentage CHECK (ownership_percentage_amount BETWEEN 0 AND 100)
);

CREATE INDEX idx_account_ownership_account ON account_ownership(account_id);
CREATE INDEX idx_account_ownership_owner ON account_ownership(owner_party_id);
CREATE INDEX idx_account_ownership_role ON account_ownership(ownership_role);
CREATE INDEX idx_account_ownership_status ON account_ownership(ownership_end_date);

-- TABLE: ACCOUNT_REGULATORY_CLASSIFICATION (Most Atomic: Part 370 ORC mapping)
-- Purpose: Captures FDIC Part 370 Ownership Right & Capacity (ORC) classification
-- Regulatory: FDIC Part 370 § 370.4(c), § 370.3(b); Part 330 § 330.1
CREATE TABLE account_regulatory_classification (
  classification_id            UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEY
  account_id                   UUID            NOT NULL UNIQUE REFERENCES account(account_id),
  
  -- ORC CODE (Per Part 370 Appendix A)
  orc_code                     orc_code_enum   NOT NULL,
  
  -- INSURANCE COVERAGE (Per Part 330)
  orc_insured_amount_per_owner NUMERIC(18, 2)  NOT NULL DEFAULT 250000.00,  -- SMDIA
  orc_insurance_category       insurance_category_enum DEFAULT 'Covered',
  
  -- CLASSIFICATION LOGIC
  orc_determination_date       DATE            NOT NULL DEFAULT CURRENT_DATE,
  orc_determination_method     orc_determination_method_enum,
  orc_verification_date        DATE            NOT NULL,
  orc_change_reason            VARCHAR(255),
  orc_change_prior_code        orc_code_enum,
  orc_change_date              DATE,
  
  -- DERIVED/CACHED FLAGS (For fast filtering; derived from ORC code)
  is_joint_ownership           BOOLEAN         NOT NULL DEFAULT FALSE,
  is_ira                       BOOLEAN         NOT NULL DEFAULT FALSE,
  is_keogh                     BOOLEAN         NOT NULL DEFAULT FALSE,
  is_trust                     BOOLEAN         NOT NULL DEFAULT FALSE,
  is_government                BOOLEAN         NOT NULL DEFAULT FALSE,
  is_business                  BOOLEAN         NOT NULL DEFAULT FALSE,
  is_payable_on_death          BOOLEAN         NOT NULL DEFAULT FALSE,
  is_transfer_on_death         BOOLEAN         NOT NULL DEFAULT FALSE,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_arc_orc_code ON account_regulatory_classification(orc_code);
CREATE INDEX idx_arc_is_joint ON account_regulatory_classification(is_joint_ownership);
CREATE INDEX idx_arc_is_trust ON account_regulatory_classification(is_trust);
CREATE INDEX idx_arc_verification_date ON account_regulatory_classification(orc_verification_date);

-- TABLE: FIDUCIARY_ARRANGEMENT (Most Atomic: Trust/Escrow/Agency)
-- Purpose: Captures trust agreements, escrow accounts, and fiduciary relationships
-- Regulatory: FDIC Part 370 § 370.5 - Fiduciary account details
CREATE TABLE fiduciary_arrangement (
  fiduciary_id                 UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEY
  account_id                   UUID            NOT NULL UNIQUE REFERENCES account(account_id),
  
  -- FIDUCIARY TYPE
  fiduciary_type               fiduciary_type_enum NOT NULL,
  
  -- DOCUMENT REFERENCES
  document_name                VARCHAR(255),
  document_date_signed         DATE,
  document_file_reference      VARCHAR(500),
  document_storage_location    VARCHAR(255),
  
  -- DOCUMENT VERIFICATION
  document_verification_date   DATE            NOT NULL,
  document_verification_method verification_method_enum,
  document_verified_by         VARCHAR(50),
  document_expiry_date         DATE,
  
  -- TRUSTEE/FIDUCIARY PARTY
  trustee_party_id             UUID            NOT NULL REFERENCES party(party_id),
  trustee_designated_date      DATE            NOT NULL,
  trustee_is_successor         BOOLEAN         DEFAULT FALSE,
  
  -- SETTLOR/GRANTOR
  settlor_party_id             UUID            REFERENCES party(party_id),
  settlor_is_deceased          BOOLEAN         DEFAULT FALSE,
  
  -- AMENDMENTS
  latest_amendment_date        DATE,
  latest_amendment_number      INT             DEFAULT 0,
  amendment_file_reference     VARCHAR(500),
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fiduciary_type ON fiduciary_arrangement(fiduciary_type);
CREATE INDEX idx_fiduciary_trustee ON fiduciary_arrangement(trustee_party_id);
CREATE INDEX idx_fiduciary_doc_verification ON fiduciary_arrangement(document_verification_date);
CREATE INDEX idx_fiduciary_amendment_date ON fiduciary_arrangement(latest_amendment_date);

-- TABLE: FIDUCIARY_BENEFICIARY (Most Atomic: Beneficiaries in Trust)
-- Purpose: Lists and tracks beneficiaries of trusts, distributions, and conditions
-- Regulatory: FDIC Part 330 § 330.10(d) - Multiple beneficiary coverage rules
CREATE TABLE fiduciary_beneficiary (
  beneficiary_id               UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEY
  fiduciary_id                 UUID            NOT NULL REFERENCES fiduciary_arrangement(fiduciary_id),
  
  -- BENEFICIARY REFERENCE
  beneficiary_party_id         UUID            REFERENCES party(party_id),
  beneficiary_party_is_unknown BOOLEAN         DEFAULT FALSE,
  
  -- BENEFICIARY IDENTITY (If unknown)
  beneficiary_identifier_text  VARCHAR(255),
  
  -- BENEFICIARY TYPE
  beneficiary_type             beneficiary_type_enum NOT NULL,
  
  -- DISTRIBUTION SHARE
  distribution_percentage      NUMERIC(6, 4)   NOT NULL,
  distribution_condition       VARCHAR(255),   -- e.g., "Upon reaching age 21"
  distribution_sequence        INT,             -- 1st tier, 2nd tier, etc.
  
  -- DESIGNATION
  designation_date             DATE            NOT NULL,
  designation_method           designation_method_enum,
  
  -- VERIFICATION
  beneficiary_verification_date DATE           NOT NULL,
  beneficiary_status           beneficiary_status_enum DEFAULT 'Active',
  beneficiary_status_as_of_date DATE,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- CONSTRAINT
  CONSTRAINT ck_distribution_percentage CHECK (distribution_percentage BETWEEN 0 AND 100)
);

CREATE INDEX idx_beneficiary_fiduciary ON fiduciary_beneficiary(fiduciary_id);
CREATE INDEX idx_beneficiary_party ON fiduciary_beneficiary(beneficiary_party_id);
CREATE INDEX idx_beneficiary_type ON fiduciary_beneficiary(beneficiary_type);
CREATE INDEX idx_beneficiary_distribution_seq ON fiduciary_beneficiary(distribution_sequence);

-- TABLE: ACCOUNT_FEATURE (Most Atomic: Sweep, POD, TOD, etc.)
-- Purpose: Captures account features (sweeps, POD/TOD, overdraft protection, etc.)
-- Regulatory: FDIC Part 370 § 370.5 - Account features affecting coverage
CREATE TABLE account_feature (
  feature_id                   UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEY
  account_id                   UUID            NOT NULL REFERENCES account(account_id),
  
  -- FEATURE TYPE
  feature_type                 account_feature_type_enum NOT NULL,
  
  -- FEATURE LIFECYCLE
  feature_effective_date       DATE            NOT NULL DEFAULT CURRENT_DATE,
  feature_end_date             DATE,
  feature_status               feature_status_enum NOT NULL DEFAULT 'Active',
  feature_termination_reason   VARCHAR(255),
  
  -- SWEEP PARAMETERS
  sweep_linked_account_id      UUID            REFERENCES account(account_id),
  sweep_trigger_amount         NUMERIC(18, 2),
  sweep_trigger_type           sweep_trigger_type_enum,
  sweep_frequency              sweep_frequency_enum,
  sweep_direction              sweep_direction_enum,
  sweep_minimum_amount         NUMERIC(18, 2),
  
  -- POD/TOD PARAMETERS
  beneficiary_party_id         UUID            REFERENCES party(party_id),
  beneficiary_designation_date DATE,
  beneficiary_designation_form VARCHAR(500),
  beneficiary_form_on_file     BOOLEAN         DEFAULT FALSE,
  beneficiary_verification_date DATE,
  
  -- OVERDRAFT PROTECTION PARAMETERS
  overdraft_linked_account_id  UUID            REFERENCES account(account_id),
  overdraft_max_amount         NUMERIC(18, 2),
  overdraft_fee_per_transaction NUMERIC(10, 2),
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_account_feature_account ON account_feature(account_id);
CREATE INDEX idx_account_feature_type ON account_feature(feature_type);
CREATE INDEX idx_account_feature_status ON account_feature(feature_status);
CREATE INDEX idx_account_feature_sweep_linked ON account_feature(sweep_linked_account_id);
CREATE INDEX idx_account_feature_beneficiary ON account_feature(beneficiary_party_id);

-- TABLE: TRANSACTION (Most Atomic: Single deposit/withdrawal/transfer)
-- Purpose: Captures all account transactions (deposits, withdrawals, interest, fees, etc.)
-- Regulatory: FDIC Part 370 § 370.4 - Transaction history for audit trail
CREATE TABLE transaction (
  transaction_id               UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEY
  account_id                   UUID            NOT NULL REFERENCES account(account_id),
  
  -- TIMING (Atomic: separate dates)
  transaction_date             DATE            NOT NULL,  -- Date transaction occurred
  transaction_time             TIME,
  transaction_date_submitted   DATE            NOT NULL,   -- Date submitted
  transaction_date_posted      DATE,           -- NULL if pending
  transaction_date_settled     DATE,
  
  -- TRANSACTION TYPE
  transaction_type             transaction_type_enum NOT NULL,
  
  -- AMOUNT
  transaction_amount           NUMERIC(18, 2)  NOT NULL,  -- Always positive; Type indicates debit
  transaction_amount_currency  CHAR(3)         NOT NULL DEFAULT 'USD',
  
  -- COUNTERPARTY
  counterparty_party_id        UUID            REFERENCES party(party_id),
  
  -- STATUS
  transaction_status           transaction_status_enum NOT NULL DEFAULT 'Pending',
  transaction_status_reason    VARCHAR(255),
  
  -- REFERENCE IDENTIFIERS
  check_number                 VARCHAR(20),
  reference_number             VARCHAR(50),
  confirmation_number          VARCHAR(50),
  ach_trace_number             VARCHAR(30),
  wire_reference               VARCHAR(100),
  
  -- DESCRIPTION
  transaction_description      VARCHAR(500),
  
  -- REVERSAL TRACKING
  original_transaction_id      UUID            REFERENCES transaction(transaction_id),
  reversal_reason              VARCHAR(255),
  reversal_date                DATE,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transaction_account ON transaction(account_id);
CREATE INDEX idx_transaction_date ON transaction(transaction_date);
CREATE INDEX idx_transaction_date_posted ON transaction(transaction_date_posted);
CREATE INDEX idx_transaction_type ON transaction(transaction_type);
CREATE INDEX idx_transaction_status ON transaction(transaction_status);

-- TABLE: DAILY_ACCOUNT_BALANCE (Most Atomic: EOD snapshot)
-- Purpose: End-of-day snapshot of account balances and reconciliation
-- Regulatory: FDIC Part 370 § 360.8 - Balance records for insurance calculation
CREATE TABLE daily_account_balance (
  account_id                   UUID            NOT NULL REFERENCES account(account_id),
  balance_as_of_date           DATE            NOT NULL,
  
  PRIMARY KEY (account_id, balance_as_of_date),
  
  -- BALANCE COMPONENTS
  balance_opening_amount       NUMERIC(18, 2)  NOT NULL,
  balance_deposits_amount      NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  balance_withdrawals_amount   NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  balance_interest_amount      NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  balance_fees_amount          NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,  -- Positive value
  balance_corrections_amount   NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  balance_closing_amount       NUMERIC(18, 2)  NOT NULL,
  
  -- ACCRUED INTEREST
  interest_accrued_not_posted  NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  interest_last_accrual_date   DATE,
  interest_accrual_days        INT,
  
  -- TRANSACTION COUNTS
  transaction_count_deposits   INT             DEFAULT 0,
  transaction_count_withdrawals INT            DEFAULT 0,
  transaction_count_other      INT             DEFAULT 0,
  
  -- GL RECONCILIATION
  gl_reconciliation_variance   NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  gl_reconciliation_status     gl_reconciliation_status_enum DEFAULT 'Pending',
  gl_reconciliation_approved_by VARCHAR(50),
  gl_reconciliation_approved_date DATE,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50),
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_daily_balance_date ON daily_account_balance(balance_as_of_date);
CREATE INDEX idx_daily_balance_gl_status ON daily_account_balance(gl_reconciliation_status);

-- TABLE: OFFICIAL_ITEMS (Most Atomic: Third-party held deposit)
-- Purpose: Tracks deposits held by third parties (brokers, custodians, escrow agents)
-- Regulatory: FDIC Part 370 § 370.4(d)(3) - Third-party deposit records
CREATE TABLE official_items (
  official_item_id             UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEY
  account_id                   UUID            NOT NULL REFERENCES account(account_id),
  
  -- CUSTODIAN INFORMATION
  custodian_id                 VARCHAR(50),    -- Third-party identifier
  custodian_name               VARCHAR(255),
  custodian_contact_info       VARCHAR(500),
  
  -- BALANCE TRACKING
  custodian_balance            NUMERIC(18, 2),
  our_record_balance           NUMERIC(18, 2),
  last_reconciliation_date     DATE            NOT NULL,
  
  -- DATA AGREEMENT
  data_agreement_on_file       BOOLEAN         DEFAULT FALSE,
  data_refresh_frequency       VARCHAR(50),    -- 'Daily', 'Monthly', etc.
  last_data_refresh_date       DATE,
  
  -- RECONCILIATION
  reconciliation_variance      NUMERIC(18, 2),
  variance_resolved_date       DATE,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_official_items_account ON official_items(account_id);
CREATE INDEX idx_official_items_reconciliation_date ON official_items(last_reconciliation_date);

-- TABLE: DEPOSIT_INSURANCE_CALCULATION (Most Atomic: Part 370 Coverage)
-- Purpose: Calculates and tracks FDIC deposit insurance coverage per Part 330
-- Regulatory: FDIC Part 370 § 370.3, § 370.4; Part 330 § 330.1 et seq.
CREATE TABLE deposit_insurance_calculation (
  calculation_id               UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEYS
  account_id                   UUID            NOT NULL REFERENCES account(account_id),
  classification_id            UUID            NOT NULL REFERENCES account_regulatory_classification(classification_id),
  
  -- CALCULATION TIMING
  calculation_date             DATE            NOT NULL DEFAULT CURRENT_DATE,
  calculation_time             TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  calculation_scenario         calculation_scenario_enum NOT NULL DEFAULT 'Normal',
  
  -- INPUT VALUES (Snapshots at time of calculation)
  input_account_balance        NUMERIC(18, 2)  NOT NULL,
  input_accrued_interest       NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  input_owner_count            INT             NOT NULL,
  input_orc                    VARCHAR(50)     NOT NULL,
  
  -- PART 330 RULES
  part_330_rules_version_date  DATE            NOT NULL,
  part_330_rules_smdia_amount  NUMERIC(18, 2)  NOT NULL DEFAULT 250000.00,
  
  -- CALCULATION OUTPUTS
  calculated_insured_amount    NUMERIC(18, 2)  NOT NULL,
  calculated_uninsured_amount  NUMERIC(18, 2)  NOT NULL,
  calculation_basis_description VARCHAR(500),
  
  -- BENEFICIARY/OWNER DETAIL
  beneficiary_count            INT,
  highest_individual_insured   NUMERIC(18, 2),
  
  -- TEST & VALIDATION
  calculation_validated        BOOLEAN         DEFAULT FALSE,
  calculation_validation_date  DATE,
  calculation_validated_by     VARCHAR(50),
  calculation_test_result      calculation_test_result_enum DEFAULT 'Manual',
  calculation_test_error_message VARCHAR(1000),
  
  -- APPROVAL
  calculation_approved_by      VARCHAR(50),
  calculation_approved_date    DATE,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- CONSTRAINT
  CONSTRAINT ck_insured_uninsured_sum CHECK (
    (calculated_insured_amount + calculated_uninsured_amount - input_account_balance) < 0.01
    OR (calculated_insured_amount + calculated_uninsured_amount - input_account_balance) > -0.01
  )
);

CREATE INDEX idx_dic_account ON deposit_insurance_calculation(account_id);
CREATE INDEX idx_dic_calculation_date ON deposit_insurance_calculation(calculation_date);
CREATE INDEX idx_dic_scenario ON deposit_insurance_calculation(calculation_scenario);
CREATE INDEX idx_dic_test_result ON deposit_insurance_calculation(calculation_test_result);

-- TABLE: KYC_CIP_VERIFICATION (Most Atomic: Know Your Customer / Customer Identification)
-- Purpose: Tracks KYC/CIP verification per FinCEN and FDIC requirements
-- Regulatory: 31 U.S.C. § 5318 (CIP); FDIC Guidance
CREATE TABLE kyc_cip_verification (
  verification_id              UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- FOREIGN KEY
  party_id                     UUID            NOT NULL REFERENCES party(party_id),
  
  -- VERIFICATION PROGRAM
  verification_program_type    verification_program_type_enum NOT NULL,
  
  -- CIP VERIFICATION METHOD
  cip_verification_method      cip_verification_method_enum NOT NULL,
  
  -- IDENTITY VERIFICATION
  identity_verified            BOOLEAN         NOT NULL DEFAULT FALSE,
  identity_verification_date   DATE            NOT NULL,
  identity_verification_score  INT,
  identity_document_1_type     VARCHAR(100),
  identity_document_1_number   VARCHAR(50),
  identity_document_1_expiry_date DATE,
  identity_document_1_file_ref VARCHAR(500),
  identity_document_2_type     VARCHAR(100),
  identity_document_2_number   VARCHAR(50),
  
  -- ADDRESS VERIFICATION
  address_verified             BOOLEAN         NOT NULL DEFAULT FALSE,
  address_verification_date    DATE,
  address_verification_method  address_verification_method_enum,
  address_verification_source  VARCHAR(255),
  
  -- SANCTIONS/AML SCREENING
  sanctions_screening_performed BOOLEAN        NOT NULL DEFAULT FALSE,
  sanctions_screening_date     DATE,
  sanctions_screening_database sanctions_database_enum,
  sanctions_screening_result   sanctions_result_enum DEFAULT 'Clear',
  sanctions_screening_hit_details VARCHAR(500),
  
  -- PEP / ADVERSE MEDIA
  pep_screening_performed      BOOLEAN         NOT NULL DEFAULT FALSE,
  pep_screening_date           DATE,
  pep_status                   pep_status_enum DEFAULT 'NotPEP',
  adverse_media_screening_performed BOOLEAN    NOT NULL DEFAULT FALSE,
  adverse_media_screening_date DATE,
  adverse_media_screening_result sanctions_result_enum DEFAULT 'Clear',
  
  -- BENEFICIAL OWNERSHIP (For business accounts)
  beneficial_owner_identified  BOOLEAN         NOT NULL DEFAULT FALSE,
  beneficial_owner_verification_date DATE,
  
  -- OVERALL STATUS
  verification_status          verification_status_enum NOT NULL DEFAULT 'Pending',
  verification_status_date     DATE            NOT NULL,
  verification_status_reason   VARCHAR(500),
  
  -- RISK RATING
  risk_rating                  risk_rating_enum DEFAULT 'Medium',
  risk_rating_date             DATE,
  risk_rating_basis            VARCHAR(500),
  
  -- APPROVAL & REVIEW
  verification_approved_by     VARCHAR(50),
  verification_approved_date   DATE,
  verification_reviewed_by     VARCHAR(50),
  verification_reviewed_date   DATE,
  
  -- AUDIT & NEXT REVIEW
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50)     NOT NULL,
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  verification_next_review_date DATE,
  
  -- UNIQUE CONSTRAINT
  UNIQUE (party_id, verification_program_type, verification_status_date)
);

CREATE INDEX idx_kyc_party ON kyc_cip_verification(party_id);
CREATE INDEX idx_kyc_status ON kyc_cip_verification(verification_status);
CREATE INDEX idx_kyc_risk_rating ON kyc_cip_verification(risk_rating);
CREATE INDEX idx_kyc_status_date ON kyc_cip_verification(verification_status_date);
CREATE INDEX idx_kyc_next_review_date ON kyc_cip_verification(verification_next_review_date);

-- TABLE: GL_DEPOSIT_CONTROL_ACCOUNT (Most Atomic: GL Reconciliation)
-- Purpose: General Ledger side of deposit account reconciliation
-- Regulatory: FDIC Part 370 § 360.8 - GL reconciliation tracking
CREATE TABLE gl_deposit_control_account (
  gl_account_id                UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- GL ACCOUNT REFERENCE
  gl_account_number            VARCHAR(20)     NOT NULL,  -- e.g., "1010" for Demand Deposits
  gl_balance_date              DATE            NOT NULL,
  
  -- GL BALANCES
  gl_total_deposit_balance     NUMERIC(18, 2)  NOT NULL,
  gl_control_total_per_core_system NUMERIC(18, 2) NOT NULL,
  
  -- RECONCILIATION
  gl_variance                  NUMERIC(18, 2)  NOT NULL DEFAULT 0.00,
  gl_reconciliation_status     gl_reconciliation_status_enum NOT NULL DEFAULT 'Pending',
  gl_reconciliation_approved_by VARCHAR(50),
  gl_reconciliation_approved_date DATE,
  
  -- AUDIT
  created_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by                   VARCHAR(50),
  modified_date                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- UNIQUE CONSTRAINT
  UNIQUE (gl_account_number, gl_balance_date)
);

CREATE INDEX idx_gl_balance_date ON gl_deposit_control_account(gl_balance_date);
CREATE INDEX idx_gl_reconciliation_status ON gl_deposit_control_account(gl_reconciliation_status);

-- ============================================================================
-- SECTION 3: GRANT PERMISSIONS (Minimal—adjust per your security policy)
-- ============================================================================

-- (Placeholder: Adjust roles and permissions per your bank's security policy)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO read_only_role;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO compliance_role;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO admin_role;

-- ============================================================================
-- SECTION 4: AUDIT LOG TABLE (Optional: For tracking all changes)
-- ============================================================================

-- Enum for audit_log.change_type (PostgreSQL native enum; not MySQL-style ENUM(...))
CREATE TYPE change_type_enum AS ENUM ('INSERT', 'UPDATE', 'DELETE');

CREATE TABLE audit_log (
  audit_log_id                 UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- CHANGE DETAILS
  table_name                   VARCHAR(100)    NOT NULL,
  primary_key_value            VARCHAR(100)    NOT NULL,
  column_name                  VARCHAR(100)    NOT NULL,
  old_value                    TEXT,
  new_value                    TEXT,
  change_type                  change_type_enum NOT NULL,
  
  -- AUDIT
  changed_date                 TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  changed_by                   VARCHAR(50)     NOT NULL
);

CREATE INDEX idx_audit_table ON audit_log(table_name);
CREATE INDEX idx_audit_date  ON audit_log(changed_date);
CREATE INDEX idx_audit_user  ON audit_log(changed_by);

-- ============================================================================
-- SECTION 5: DATA DICTIONARY VIEW (For documentation)
-- ============================================================================

CREATE VIEW v_data_dictionary AS
SELECT
  t.table_name,
  c.column_name,
  c.data_type,
  CASE WHEN c.is_nullable = 'NO' THEN 'NOT NULL' ELSE 'NULLABLE' END as nullability,
  col_description(format('%I.%I', t.table_schema, t.table_name)::regclass, c.ordinal_position) as column_comment
FROM information_schema.tables t
JOIN information_schema.columns c ON t.table_schema = c.table_schema AND t.table_name = c.table_name
WHERE t.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name, c.ordinal_position;

-- ============================================================================
-- SECTION 6: SAMPLE DOCUMENTATION COMMENTS
-- ============================================================================

COMMENT ON TABLE party IS
  'ATOMIC ENTITY: Party (Individual, Organization, Government)
   Regulatory: FinCEN CIP (31 U.S.C. § 5318)
   Purpose: Single source of truth for all customer and counterparty identities
   Normalization: Individual attributes only apply if party_type = ''Individual''; etc.';

COMMENT ON TABLE account IS
  'ATOMIC ENTITY: Deposit Account
   Regulatory: FDIC Part 370 § 370.4, § 370.3(a)
   Purpose: Core deposit account records with complete attribute decomposition
   Design: Balance tracking separated (current_balance + current_balance_date); Interest attributes atomic';

COMMENT ON TABLE account_regulatory_classification IS
  'ATOMIC ENTITY: Account Regulatory Classification (ORC)
   Regulatory: FDIC Part 370 § 370.4(c), Appendix A; FDIC Part 330 § 330.1
   Purpose: Ownership Right & Capacity (ORC) classification for deposit insurance determination
   Design: Boolean flags (is_joint_ownership, is_trust, etc.) derived from orc_code for fast filtering';

COMMENT ON TABLE deposit_insurance_calculation IS
  'ATOMIC ENTITY: Deposit Insurance Calculation
   Regulatory: FDIC Part 370 § 370.3(a)–(b); FDIC Part 330 § 330.1 et seq.
   Purpose: Calculate and audit FDIC coverage per Part 330 rules
   Design: Input snapshots (input_account_balance, input_owner_count) separate from calculated outputs';

COMMENT ON COLUMN account.current_balance IS
  'Point-in-time balance as of current_balance_date (typically prior business day EOD)';

COMMENT ON COLUMN account_regulatory_classification.orc_code IS
  'Ownership Right & Capacity code per FDIC Part 370 Appendix A
   Determines deposit insurance coverage calculation per FDIC Part 330 rules
   Part 330 Standard: $250,000 per depositor per ORC per institution';

COMMENT ON COLUMN account_regulatory_classification.orc_insured_amount_per_owner IS
  'Standard Maximum Deposit Insurance Amount (SMDIA) per owner under this ORC
   Current standard: $250,000 (may change per legislative action)
   Reference: 12 U.S.C. § 1821(a)(2)(D)';

COMMENT ON COLUMN fiduciary_arrangement.document_verification_date IS
  'Date trust agreement was last reviewed and verified
   FDIC Part 370 requires verification; recommend annual review (≤24 months old)';

COMMENT ON COLUMN fiduciary_beneficiary.distribution_percentage IS
  'Beneficiary''s percentage share of trust (0–100)
   For named beneficiaries: each gets separate $250,000 coverage (max 5)
   Sum of all beneficiaries for a trust should = 100% (or <100% if intentional)';

COMMENT ON COLUMN account_feature.feature_type IS
  'Account feature type (Sweep, POD, TOD, etc.)
   Each feature_type has specific parameters (e.g., sweep_linked_account_id for Sweep features)';

COMMENT ON COLUMN kyc_cip_verification.verification_status IS
  'Overall KYC/CIP verification status
   Values: Complete (approved), Pending (in progress), Failed (did not pass), Exception (manual review), Manual_Review
   Account opening should NOT be allowed if verification_status ≠ Complete';

-- ============================================================================
-- END OF DDL SCRIPT
-- ============================================================================
-- 
-- NEXT STEPS:
-- 1. Execute this script in your PostgreSQL database
-- 2. Adjust GRANT statements per your bank''s security policy
-- 3. Create VIEWS for composite features (see Data Dictionary document)
-- 4. Load sample/production data using INSERT statements
-- 5. Run validation queries (see Data Control Mapping section)
-- 6. Configure automated audit triggers (optional)
--
-- ============================================================================
