-- ============================================================================
-- ATOMIC DEPOSIT SYSTEM — DEMO SEED DATA
-- Task 1: Realistic INSERT statements for 5-account, 4-party demo
-- Date:   2026-02-27
-- Reg:    FDIC Part 370 / Part 330; FinCEN CIP (31 U.S.C. § 5318)
-- ============================================================================
-- Run against: atomic_deposit_system  (PostgreSQL 14+)
-- Prereq:      01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql must be executed first
-- ============================================================================

BEGIN;

DO $$
DECLARE
  -- ── Party UUIDs ──────────────────────────────────────────────────────────
  v_party_john    UUID;
  v_party_jane    UUID;
  v_party_robert  UUID;
  v_party_abc     UUID;

  -- ── Account UUIDs ────────────────────────────────────────────────────────
  v_acct_savings  UUID;
  v_acct_checking UUID;
  v_acct_joint    UUID;
  v_acct_trust    UUID;
  v_acct_ira      UUID;

  -- ── Classification UUIDs ─────────────────────────────────────────────────
  v_cls_savings   UUID;
  v_cls_checking  UUID;
  v_cls_joint     UUID;
  v_cls_trust     UUID;
  v_cls_ira       UUID;

  -- ── Fiduciary UUID ───────────────────────────────────────────────────────
  v_fid_trust     UUID;

  -- ── Reference dates ──────────────────────────────────────────────────────
  v_open_date         CONSTANT DATE := '2024-01-15';
  v_kyc_date          CONSTANT DATE := '2024-01-10';
  v_balance_date      CONSTANT DATE := '2026-02-26';   -- yesterday EOD
  v_today             CONSTANT DATE := '2026-02-27';
  v_next_review       CONSTANT DATE := '2027-02-27';
  v_part330_version   CONSTANT DATE := '2023-01-01';

BEGIN

  -- ==========================================================================
  -- SECTION 1: PARTIES
  -- ==========================================================================

  -- Individual 1: John Smith
  INSERT INTO party (
    party_type, party_status,
    individual_name_given, individual_name_middle, individual_name_family,
    individual_date_of_birth, individual_ssn,
    address_street_line1, address_city, address_state_province,
    address_postal_code, address_country, address_is_usa,
    phone_number_primary, email_primary,
    created_by, modified_by
  ) VALUES (
    'Individual', 'Active',
    'John', 'Michael', 'Smith',
    '1975-04-22', '111223333',
    '100 Park Avenue', 'New York', 'NY',
    '10017', 'US', TRUE,
    '+1-212-555-0101', 'john.smith@email.com',
    'seed_admin', 'seed_admin'
  )
  RETURNING party_id INTO v_party_john;

  -- Individual 2: Jane Doe
  INSERT INTO party (
    party_type, party_status,
    individual_name_given, individual_name_family,
    individual_date_of_birth, individual_ssn,
    address_street_line1, address_city, address_state_province,
    address_postal_code, address_country, address_is_usa,
    phone_number_primary, email_primary,
    created_by, modified_by
  ) VALUES (
    'Individual', 'Active',
    'Jane', 'Doe',
    '1982-08-14', '222334444',
    '200 Lexington Avenue', 'New York', 'NY',
    '10016', 'US', TRUE,
    '+1-212-555-0202', 'jane.doe@email.com',
    'seed_admin', 'seed_admin'
  )
  RETURNING party_id INTO v_party_jane;

  -- Individual 3: Robert Chen
  INSERT INTO party (
    party_type, party_status,
    individual_name_given, individual_name_family,
    individual_date_of_birth, individual_ssn,
    address_street_line1, address_city, address_state_province,
    address_postal_code, address_country, address_is_usa,
    phone_number_primary, email_primary,
    created_by, modified_by
  ) VALUES (
    'Individual', 'Active',
    'Robert', 'Chen',
    '1968-11-30', '333445555',
    '350 Fifth Avenue', 'New York', 'NY',
    '10118', 'US', TRUE,
    '+1-212-555-0303', 'robert.chen@email.com',
    'seed_admin', 'seed_admin'
  )
  RETURNING party_id INTO v_party_robert;

  -- Organization: ABC Corp
  INSERT INTO party (
    party_type, party_status,
    organization_legal_name, organization_tax_id,
    organization_type, organization_country_of_inc, organization_state_of_inc,
    address_street_line1, address_city, address_state_province,
    address_postal_code, address_country, address_is_usa,
    phone_number_primary, email_primary,
    created_by, modified_by
  ) VALUES (
    'Organization', 'Active',
    'ABC Corporation', '12-3456789',
    'Corporation', 'US', 'DE',
    '1 World Trade Center', 'New York', 'NY',
    '10007', 'US', TRUE,
    '+1-212-555-0404', 'info@abccorp.com',
    'seed_admin', 'seed_admin'
  )
  RETURNING party_id INTO v_party_abc;

  -- ==========================================================================
  -- SECTION 2: ACCOUNTS
  -- ==========================================================================
  -- Per FDIC Part 370 § 370.4(a): account records must include account_type,
  -- account_open_date, and primary_owner_party_id at a minimum.

  -- Account 1: Savings — John Smith (Single ORC)
  INSERT INTO account (
    account_number, account_type, account_status,
    account_open_date, primary_owner_party_id,
    interest_rate_percentage, interest_rate_effective_date,
    interest_calculation_method, interest_compounding_freq, interest_calculation_basis,
    interest_last_accrual_date,
    current_balance, current_balance_date, accrued_interest_not_posted,
    minimum_balance,
    created_by, modified_by
  ) VALUES (
    'SAV-001-2024', 'Savings', 'Active',
    v_open_date, v_party_john,
    2.5000, v_open_date,
    'Daily', 'Monthly', '365-Day',
    v_balance_date,
    15000.00, v_balance_date, 3.12,
    0.00,
    'seed_admin', 'seed_admin'
  )
  RETURNING account_id INTO v_acct_savings;

  -- Account 2: Checking — Jane Doe (Single ORC)
  INSERT INTO account (
    account_number, account_type, account_status,
    account_open_date, primary_owner_party_id,
    interest_rate_percentage, interest_rate_effective_date,
    current_balance, current_balance_date, accrued_interest_not_posted,
    minimum_balance,
    created_by, modified_by
  ) VALUES (
    'CHK-001-2024', 'Checking', 'Active',
    v_open_date, v_party_jane,
    0.0000, v_open_date,
    8500.00, v_balance_date, 0.00,
    0.00,
    'seed_admin', 'seed_admin'
  )
  RETURNING account_id INTO v_acct_checking;

  -- Account 3: Joint JTWROS — John Smith + Jane Doe
  INSERT INTO account (
    account_number, account_type, account_status,
    account_open_date, primary_owner_party_id,
    interest_rate_percentage, interest_rate_effective_date,
    interest_calculation_method, interest_compounding_freq, interest_calculation_basis,
    interest_last_accrual_date,
    current_balance, current_balance_date, accrued_interest_not_posted,
    minimum_balance,
    created_by, modified_by
  ) VALUES (
    'JNT-001-2024', 'Savings', 'Active',
    v_open_date, v_party_john,
    2.0000, v_open_date,
    'Daily', 'Monthly', '365-Day',
    v_balance_date,
    350000.00, v_balance_date, 72.60,
    0.00,
    'seed_admin', 'seed_admin'
  )
  RETURNING account_id INTO v_acct_joint;

  -- Account 4: Trust Account (Revocable) — John Smith trustee
  INSERT INTO account (
    account_number, account_type, account_status,
    account_open_date, primary_owner_party_id,
    interest_rate_percentage, interest_rate_effective_date,
    interest_calculation_method, interest_compounding_freq, interest_calculation_basis,
    interest_last_accrual_date,
    current_balance, current_balance_date, accrued_interest_not_posted,
    minimum_balance,
    created_by, modified_by
  ) VALUES (
    'TRU-001-2024', 'Trust Account', 'Active',
    v_open_date, v_party_john,
    3.0000, v_open_date,
    'Daily', 'Quarterly', '365-Day',
    v_balance_date,
    200000.00, v_balance_date, 147.95,
    0.00,
    'seed_admin', 'seed_admin'
  )
  RETURNING account_id INTO v_acct_trust;

  -- Account 5: IRA Traditional — Robert Chen
  INSERT INTO account (
    account_number, account_type, account_status,
    account_open_date, primary_owner_party_id,
    interest_rate_percentage, interest_rate_effective_date,
    interest_calculation_method, interest_compounding_freq, interest_calculation_basis,
    interest_last_accrual_date,
    current_balance, current_balance_date, accrued_interest_not_posted,
    minimum_balance,
    created_by, modified_by
  ) VALUES (
    'IRA-001-2024', 'Individual Retirement Account', 'Active',
    v_open_date, v_party_robert,
    4.0000, v_open_date,
    'Compound', 'Annually', '365-Day',
    v_balance_date,
    75000.00, v_balance_date, 8.22,
    0.00,
    'seed_admin', 'seed_admin'
  )
  RETURNING account_id INTO v_acct_ira;

  -- ==========================================================================
  -- SECTION 3: ACCOUNT OWNERSHIP
  -- ==========================================================================
  -- Per FDIC Part 370 § 370.4(c): Ownership Right & Capacity recorded per owner.

  -- Savings → John Smith (sole PrimaryOwner, 100%)
  INSERT INTO account_ownership (
    account_id, owner_party_id, ownership_role,
    ownership_percentage_amount, ownership_effective_date,
    ownership_verification_date, ownership_verification_method,
    created_by
  ) VALUES (
    v_acct_savings, v_party_john, 'PrimaryOwner',
    100.00, v_open_date,
    v_open_date, 'DocumentReview',
    'seed_admin'
  );

  -- Checking → Jane Doe (sole PrimaryOwner, 100%)
  INSERT INTO account_ownership (
    account_id, owner_party_id, ownership_role,
    ownership_percentage_amount, ownership_effective_date,
    ownership_verification_date, ownership_verification_method,
    created_by
  ) VALUES (
    v_acct_checking, v_party_jane, 'PrimaryOwner',
    100.00, v_open_date,
    v_open_date, 'DocumentReview',
    'seed_admin'
  );

  -- Joint JTWROS → John Smith (PrimaryOwner, 50%) + Jane Doe (JointOwner, 50%)
  INSERT INTO account_ownership (
    account_id, owner_party_id, ownership_role,
    ownership_percentage_amount, ownership_effective_date,
    ownership_verification_date, ownership_verification_method,
    created_by
  ) VALUES (
    v_acct_joint, v_party_john, 'PrimaryOwner',
    50.00, v_open_date,
    v_open_date, 'SignedAgreement',
    'seed_admin'
  );

  INSERT INTO account_ownership (
    account_id, owner_party_id, ownership_role,
    ownership_percentage_amount, ownership_effective_date,
    ownership_verification_date, ownership_verification_method,
    created_by
  ) VALUES (
    v_acct_joint, v_party_jane, 'JointOwner',
    50.00, v_open_date,
    v_open_date, 'SignedAgreement',
    'seed_admin'
  );

  -- Trust → John Smith (Trustee, 100% legal title)
  INSERT INTO account_ownership (
    account_id, owner_party_id, ownership_role,
    ownership_percentage_amount, ownership_effective_date,
    ownership_verification_date, ownership_verification_method,
    created_by
  ) VALUES (
    v_acct_trust, v_party_john, 'Trustee',
    100.00, v_open_date,
    v_open_date, 'SignedAgreement',
    'seed_admin'
  );

  -- IRA → Robert Chen (sole PrimaryOwner, 100%)
  INSERT INTO account_ownership (
    account_id, owner_party_id, ownership_role,
    ownership_percentage_amount, ownership_effective_date,
    ownership_verification_date, ownership_verification_method,
    created_by
  ) VALUES (
    v_acct_ira, v_party_robert, 'PrimaryOwner',
    100.00, v_open_date,
    v_open_date, 'DocumentReview',
    'seed_admin'
  );

  -- ==========================================================================
  -- SECTION 4: ACCOUNT REGULATORY CLASSIFICATION (ORC)
  -- ==========================================================================
  -- Per FDIC Part 370 § 370.3(b) / Appendix A: ORC code assigned at opening.

  -- Savings → Single (ORC 01 equivalent)
  INSERT INTO account_regulatory_classification (
    account_id, orc_code,
    orc_insured_amount_per_owner, orc_insurance_category,
    orc_determination_date, orc_determination_method, orc_verification_date,
    is_joint_ownership, is_ira, is_keogh, is_trust, is_government, is_business,
    is_payable_on_death, is_transfer_on_death,
    created_by
  ) VALUES (
    v_acct_savings, 'Single',
    250000.00, 'Covered',
    v_open_date, 'RegistrationForm', v_today,
    FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE,
    'seed_admin'
  )
  RETURNING classification_id INTO v_cls_savings;

  -- Checking → Single
  INSERT INTO account_regulatory_classification (
    account_id, orc_code,
    orc_insured_amount_per_owner, orc_insurance_category,
    orc_determination_date, orc_determination_method, orc_verification_date,
    is_joint_ownership, is_ira, is_keogh, is_trust, is_government, is_business,
    is_payable_on_death, is_transfer_on_death,
    created_by
  ) VALUES (
    v_acct_checking, 'Single',
    250000.00, 'Covered',
    v_open_date, 'RegistrationForm', v_today,
    FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE,
    'seed_admin'
  )
  RETURNING classification_id INTO v_cls_checking;

  -- Joint → Joint_JTWROS   (is_joint_ownership = TRUE)
  INSERT INTO account_regulatory_classification (
    account_id, orc_code,
    orc_insured_amount_per_owner, orc_insurance_category,
    orc_determination_date, orc_determination_method, orc_verification_date,
    is_joint_ownership, is_ira, is_keogh, is_trust, is_government, is_business,
    is_payable_on_death, is_transfer_on_death,
    created_by
  ) VALUES (
    v_acct_joint, 'Joint_JTWROS',
    250000.00, 'Covered',
    v_open_date, 'RegistrationForm', v_today,
    TRUE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE,
    'seed_admin'
  )
  RETURNING classification_id INTO v_cls_joint;

  -- Trust → Trust_Revocable  (is_trust = TRUE)
  INSERT INTO account_regulatory_classification (
    account_id, orc_code,
    orc_insured_amount_per_owner, orc_insurance_category,
    orc_determination_date, orc_determination_method, orc_verification_date,
    is_joint_ownership, is_ira, is_keogh, is_trust, is_government, is_business,
    is_payable_on_death, is_transfer_on_death,
    created_by
  ) VALUES (
    v_acct_trust, 'Trust_Revocable',
    250000.00, 'Covered',
    v_open_date, 'TrustDocument', v_today,
    FALSE, FALSE, FALSE, TRUE, FALSE, FALSE, FALSE, FALSE,
    'seed_admin'
  )
  RETURNING classification_id INTO v_cls_trust;

  -- IRA → IRA_Traditional  (is_ira = TRUE; separate coverage per Part 330 § 330.14)
  INSERT INTO account_regulatory_classification (
    account_id, orc_code,
    orc_insured_amount_per_owner, orc_insurance_category,
    orc_determination_date, orc_determination_method, orc_verification_date,
    is_joint_ownership, is_ira, is_keogh, is_trust, is_government, is_business,
    is_payable_on_death, is_transfer_on_death,
    created_by
  ) VALUES (
    v_acct_ira, 'IRA_Traditional',
    250000.00, 'Covered',
    v_open_date, 'RegistrationForm', v_today,
    FALSE, TRUE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE,
    'seed_admin'
  )
  RETURNING classification_id INTO v_cls_ira;

  -- ==========================================================================
  -- SECTION 5: FIDUCIARY ARRANGEMENT + BENEFICIARIES
  -- ==========================================================================
  -- Per FDIC Part 330 § 330.10(d): revocable trust coverage is $250K per
  -- named beneficiary (up to 5 beneficiaries, capped at $1.25M total).

  INSERT INTO fiduciary_arrangement (
    account_id, fiduciary_type,
    document_name, document_date_signed,
    document_file_reference, document_storage_location,
    document_verification_date, document_verification_method, document_verified_by,
    trustee_party_id, trustee_designated_date, trustee_is_successor,
    settlor_party_id, settlor_is_deceased,
    created_by
  ) VALUES (
    v_acct_trust, 'Trust_Revocable',
    'John Smith Revocable Living Trust', '2024-01-10',
    'trusts/trust_001_executed.pdf', 'secure-vault/trusts',
    '2024-01-15', 'DocumentReview', 'seed_admin',
    v_party_john, v_open_date, FALSE,
    v_party_john, FALSE,
    'seed_admin'
  )
  RETURNING fiduciary_id INTO v_fid_trust;

  -- Beneficiary 1: Jane Doe (50%)
  INSERT INTO fiduciary_beneficiary (
    fiduciary_id, beneficiary_party_id,
    beneficiary_type, distribution_percentage,
    distribution_condition, distribution_sequence,
    designation_date, designation_method,
    beneficiary_verification_date, beneficiary_status
  ) VALUES (
    v_fid_trust, v_party_jane,
    'Individual', 50.0000,
    'Immediate', 1,
    '2024-01-15', 'TrustDocument',
    '2024-01-15', 'Active'
  );

  -- Beneficiary 2: Robert Chen (50%)
  INSERT INTO fiduciary_beneficiary (
    fiduciary_id, beneficiary_party_id,
    beneficiary_type, distribution_percentage,
    distribution_condition, distribution_sequence,
    designation_date, designation_method,
    beneficiary_verification_date, beneficiary_status
  ) VALUES (
    v_fid_trust, v_party_robert,
    'Individual', 50.0000,
    'Immediate', 2,
    '2024-01-15', 'TrustDocument',
    '2024-01-15', 'Active'
  );

  -- ==========================================================================
  -- SECTION 6: KYC / CIP VERIFICATION
  -- ==========================================================================
  -- Per FinCEN CIP (31 U.S.C. § 5318): identity verification required for all
  -- individual parties before account opening.

  -- KYC for John Smith
  INSERT INTO kyc_cip_verification (
    party_id, verification_program_type, cip_verification_method,
    identity_verified, identity_verification_date,
    identity_document_1_type, identity_document_1_number, identity_document_1_expiry_date,
    address_verified, address_verification_date, address_verification_method,
    sanctions_screening_performed, sanctions_screening_date,
    sanctions_screening_database, sanctions_screening_result,
    pep_screening_performed, pep_screening_date, pep_status,
    adverse_media_screening_performed, adverse_media_screening_date,
    adverse_media_screening_result,
    beneficial_owner_identified,
    verification_status, verification_status_date,
    risk_rating, risk_rating_date, risk_rating_basis,
    verification_next_review_date,
    created_by
  ) VALUES (
    v_party_john, 'CIP', 'DocumentReview_DriversLicense',
    TRUE, v_kyc_date,
    'Drivers License', 'NY-DL-12345678', '2030-04-22',
    TRUE, v_kyc_date, 'DocumentReview',
    TRUE, v_kyc_date,
    'OFAC', 'Clear',
    TRUE, v_kyc_date, 'NotPEP',
    TRUE, v_kyc_date,
    'Clear',
    FALSE,
    'Complete', v_kyc_date,
    'Low', v_kyc_date, 'Standard CIP; clean OFAC; no PEP; low-risk profile',
    v_next_review,
    'seed_admin'
  );

  -- KYC for Jane Doe
  INSERT INTO kyc_cip_verification (
    party_id, verification_program_type, cip_verification_method,
    identity_verified, identity_verification_date,
    identity_document_1_type, identity_document_1_number, identity_document_1_expiry_date,
    address_verified, address_verification_date, address_verification_method,
    sanctions_screening_performed, sanctions_screening_date,
    sanctions_screening_database, sanctions_screening_result,
    pep_screening_performed, pep_screening_date, pep_status,
    adverse_media_screening_performed, adverse_media_screening_date,
    adverse_media_screening_result,
    beneficial_owner_identified,
    verification_status, verification_status_date,
    risk_rating, risk_rating_date, risk_rating_basis,
    verification_next_review_date,
    created_by
  ) VALUES (
    v_party_jane, 'CIP', 'DocumentReview_DriversLicense',
    TRUE, v_kyc_date,
    'Drivers License', 'NY-DL-98765432', '2028-08-14',
    TRUE, v_kyc_date, 'DocumentReview',
    TRUE, v_kyc_date,
    'OFAC', 'Clear',
    TRUE, v_kyc_date, 'NotPEP',
    TRUE, v_kyc_date,
    'Clear',
    FALSE,
    'Complete', v_kyc_date,
    'Low', v_kyc_date, 'Standard CIP; clean OFAC; no PEP; low-risk profile',
    v_next_review,
    'seed_admin'
  );

  -- KYC for Robert Chen
  INSERT INTO kyc_cip_verification (
    party_id, verification_program_type, cip_verification_method,
    identity_verified, identity_verification_date,
    identity_document_1_type, identity_document_1_number, identity_document_1_expiry_date,
    address_verified, address_verification_date, address_verification_method,
    sanctions_screening_performed, sanctions_screening_date,
    sanctions_screening_database, sanctions_screening_result,
    pep_screening_performed, pep_screening_date, pep_status,
    adverse_media_screening_performed, adverse_media_screening_date,
    adverse_media_screening_result,
    beneficial_owner_identified,
    verification_status, verification_status_date,
    risk_rating, risk_rating_date, risk_rating_basis,
    verification_next_review_date,
    created_by
  ) VALUES (
    v_party_robert, 'CIP', 'DocumentReview_DriversLicense',
    TRUE, v_kyc_date,
    'Drivers License', 'NY-DL-55544433', '2027-11-30',
    TRUE, v_kyc_date, 'DocumentReview',
    TRUE, v_kyc_date,
    'OFAC', 'Clear',
    TRUE, v_kyc_date, 'NotPEP',
    TRUE, v_kyc_date,
    'Clear',
    FALSE,
    'Complete', v_kyc_date,
    'Low', v_kyc_date, 'Standard CIP; clean OFAC; no adverse media',
    v_next_review,
    'seed_admin'
  );

  -- ==========================================================================
  -- SECTION 7: DAILY ACCOUNT BALANCE (yesterday EOD, 2026-02-26)
  -- ==========================================================================
  -- Per FDIC Part 370 § 360.8: daily balance snapshots required.
  -- All 5 accounts reconciled, variance = 0.

  -- Savings balance snapshot
  INSERT INTO daily_account_balance (
    account_id, balance_as_of_date,
    balance_opening_amount, balance_deposits_amount, balance_withdrawals_amount,
    balance_interest_amount, balance_fees_amount, balance_corrections_amount,
    balance_closing_amount,
    interest_accrued_not_posted, interest_last_accrual_date, interest_accrual_days,
    transaction_count_deposits, transaction_count_withdrawals, transaction_count_other,
    gl_reconciliation_variance, gl_reconciliation_status,
    gl_reconciliation_approved_by, gl_reconciliation_approved_date,
    created_by
  ) VALUES (
    v_acct_savings, v_balance_date,
    15000.00, 0.00, 0.00, 1.03, 0.00, 0.00,
    15001.03,
    3.12, v_balance_date, 1,
    0, 0, 1,
    0.00, 'Reconciled',
    'seed_admin', v_balance_date,
    'seed_admin'
  );

  -- Checking balance snapshot
  INSERT INTO daily_account_balance (
    account_id, balance_as_of_date,
    balance_opening_amount, balance_deposits_amount, balance_withdrawals_amount,
    balance_interest_amount, balance_fees_amount, balance_corrections_amount,
    balance_closing_amount,
    interest_accrued_not_posted, interest_last_accrual_date, interest_accrual_days,
    transaction_count_deposits, transaction_count_withdrawals, transaction_count_other,
    gl_reconciliation_variance, gl_reconciliation_status,
    gl_reconciliation_approved_by, gl_reconciliation_approved_date,
    created_by
  ) VALUES (
    v_acct_checking, v_balance_date,
    8500.00, 0.00, 0.00, 0.00, 0.00, 0.00,
    8500.00,
    0.00, v_balance_date, 1,
    0, 0, 0,
    0.00, 'Reconciled',
    'seed_admin', v_balance_date,
    'seed_admin'
  );

  -- Joint balance snapshot
  INSERT INTO daily_account_balance (
    account_id, balance_as_of_date,
    balance_opening_amount, balance_deposits_amount, balance_withdrawals_amount,
    balance_interest_amount, balance_fees_amount, balance_corrections_amount,
    balance_closing_amount,
    interest_accrued_not_posted, interest_last_accrual_date, interest_accrual_days,
    transaction_count_deposits, transaction_count_withdrawals, transaction_count_other,
    gl_reconciliation_variance, gl_reconciliation_status,
    gl_reconciliation_approved_by, gl_reconciliation_approved_date,
    created_by
  ) VALUES (
    v_acct_joint, v_balance_date,
    350000.00, 0.00, 0.00, 19.18, 0.00, 0.00,
    350019.18,
    72.60, v_balance_date, 1,
    0, 0, 1,
    0.00, 'Reconciled',
    'seed_admin', v_balance_date,
    'seed_admin'
  );

  -- Trust balance snapshot
  INSERT INTO daily_account_balance (
    account_id, balance_as_of_date,
    balance_opening_amount, balance_deposits_amount, balance_withdrawals_amount,
    balance_interest_amount, balance_fees_amount, balance_corrections_amount,
    balance_closing_amount,
    interest_accrued_not_posted, interest_last_accrual_date, interest_accrual_days,
    transaction_count_deposits, transaction_count_withdrawals, transaction_count_other,
    gl_reconciliation_variance, gl_reconciliation_status,
    gl_reconciliation_approved_by, gl_reconciliation_approved_date,
    created_by
  ) VALUES (
    v_acct_trust, v_balance_date,
    200000.00, 0.00, 0.00, 16.44, 0.00, 0.00,
    200016.44,
    147.95, v_balance_date, 1,
    0, 0, 1,
    0.00, 'Reconciled',
    'seed_admin', v_balance_date,
    'seed_admin'
  );

  -- IRA balance snapshot
  INSERT INTO daily_account_balance (
    account_id, balance_as_of_date,
    balance_opening_amount, balance_deposits_amount, balance_withdrawals_amount,
    balance_interest_amount, balance_fees_amount, balance_corrections_amount,
    balance_closing_amount,
    interest_accrued_not_posted, interest_last_accrual_date, interest_accrual_days,
    transaction_count_deposits, transaction_count_withdrawals, transaction_count_other,
    gl_reconciliation_variance, gl_reconciliation_status,
    gl_reconciliation_approved_by, gl_reconciliation_approved_date,
    created_by
  ) VALUES (
    v_acct_ira, v_balance_date,
    75000.00, 0.00, 0.00, 8.22, 0.00, 0.00,
    75008.22,
    8.22, v_balance_date, 1,
    0, 0, 1,
    0.00, 'Reconciled',
    'seed_admin', v_balance_date,
    'seed_admin'
  );

  -- ==========================================================================
  -- SECTION 8: DEPOSIT INSURANCE CALCULATIONS
  -- ==========================================================================
  -- Per FDIC Part 330 § 330.1 et seq.:
  --   Single/IRA  → min(balance, $250,000)
  --   Joint JTWROS → min(balance, $250,000 × owner_count)
  --   Trust Rev.  → min(balance, $250,000 × min(beneficiary_count, 5))

  -- Savings: Single, balance = $15,000 → insured = $15,000
  INSERT INTO deposit_insurance_calculation (
    account_id, classification_id,
    calculation_date, calculation_scenario,
    input_account_balance, input_accrued_interest,
    input_owner_count, input_orc,
    part_330_rules_version_date, part_330_rules_smdia_amount,
    calculated_insured_amount, calculated_uninsured_amount,
    calculation_basis_description, beneficiary_count,
    calculation_test_result,
    calculation_validated, calculation_validation_date, calculation_validated_by
  ) VALUES (
    v_acct_savings, v_cls_savings,
    v_today, 'Normal',
    15000.00, 3.12,
    1, 'Single',
    v_part330_version, 250000.00,
    15000.00, 0.00,
    'Single account: min(15000, 250000) = 15000. Per FDIC Part 330 § 330.9.',
    0,
    'Pass',
    TRUE, v_today, 'seed_admin'
  );

  -- Checking: Single, balance = $8,500 → insured = $8,500
  INSERT INTO deposit_insurance_calculation (
    account_id, classification_id,
    calculation_date, calculation_scenario,
    input_account_balance, input_accrued_interest,
    input_owner_count, input_orc,
    part_330_rules_version_date, part_330_rules_smdia_amount,
    calculated_insured_amount, calculated_uninsured_amount,
    calculation_basis_description, beneficiary_count,
    calculation_test_result,
    calculation_validated, calculation_validation_date, calculation_validated_by
  ) VALUES (
    v_acct_checking, v_cls_checking,
    v_today, 'Normal',
    8500.00, 0.00,
    1, 'Single',
    v_part330_version, 250000.00,
    8500.00, 0.00,
    'Single account: min(8500, 250000) = 8500. Per FDIC Part 330 § 330.9.',
    0,
    'Pass',
    TRUE, v_today, 'seed_admin'
  );

  -- Joint JTWROS: 2 owners, balance = $350,000 → cap = 500,000 → insured = $350,000
  INSERT INTO deposit_insurance_calculation (
    account_id, classification_id,
    calculation_date, calculation_scenario,
    input_account_balance, input_accrued_interest,
    input_owner_count, input_orc,
    part_330_rules_version_date, part_330_rules_smdia_amount,
    calculated_insured_amount, calculated_uninsured_amount,
    calculation_basis_description, beneficiary_count,
    calculation_test_result,
    calculation_validated, calculation_validation_date, calculation_validated_by
  ) VALUES (
    v_acct_joint, v_cls_joint,
    v_today, 'Normal',
    350000.00, 72.60,
    2, 'Joint_JTWROS',
    v_part330_version, 250000.00,
    350000.00, 0.00,
    'Joint JTWROS: min(350000, 250000 × 2) = min(350000, 500000) = 350000. Per FDIC Part 330 § 330.9.',
    0,
    'Pass',
    TRUE, v_today, 'seed_admin'
  );

  -- Trust Revocable: 2 beneficiaries, balance = $200,000 → cap = 500,000 → insured = $200,000
  INSERT INTO deposit_insurance_calculation (
    account_id, classification_id,
    calculation_date, calculation_scenario,
    input_account_balance, input_accrued_interest,
    input_owner_count, input_orc,
    part_330_rules_version_date, part_330_rules_smdia_amount,
    calculated_insured_amount, calculated_uninsured_amount,
    calculation_basis_description, beneficiary_count,
    calculation_test_result,
    calculation_validated, calculation_validation_date, calculation_validated_by
  ) VALUES (
    v_acct_trust, v_cls_trust,
    v_today, 'Normal',
    200000.00, 147.95,
    1, 'Trust_Revocable',
    v_part330_version, 250000.00,
    200000.00, 0.00,
    'Trust Revocable: 2 named beneficiaries; min(200000, 250000 × min(2,5)) = min(200000, 500000) = 200000. Per FDIC Part 330 § 330.10(d).',
    2,
    'Pass',
    TRUE, v_today, 'seed_admin'
  );

  -- IRA Traditional: balance = $75,000 → insured = $75,000 (separate coverage per § 330.14)
  INSERT INTO deposit_insurance_calculation (
    account_id, classification_id,
    calculation_date, calculation_scenario,
    input_account_balance, input_accrued_interest,
    input_owner_count, input_orc,
    part_330_rules_version_date, part_330_rules_smdia_amount,
    calculated_insured_amount, calculated_uninsured_amount,
    calculation_basis_description, beneficiary_count,
    calculation_test_result,
    calculation_validated, calculation_validation_date, calculation_validated_by
  ) VALUES (
    v_acct_ira, v_cls_ira,
    v_today, 'Normal',
    75000.00, 8.22,
    1, 'IRA_Traditional',
    v_part330_version, 250000.00,
    75000.00, 0.00,
    'IRA Traditional: min(75000, 250000) = 75000. Separate $250K coverage per FDIC Part 330 § 330.14.',
    0,
    'Pass',
    TRUE, v_today, 'seed_admin'
  );

END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Party count
SELECT party_type, COUNT(*) AS cnt FROM party GROUP BY party_type ORDER BY party_type;

-- Account summary with ORC codes
SELECT
  a.account_number,
  a.account_type,
  a.current_balance,
  arc.orc_code,
  dic.calculated_insured_amount,
  dic.calculated_uninsured_amount,
  dic.calculation_test_result
FROM account a
JOIN account_regulatory_classification arc ON arc.account_id = a.account_id
JOIN deposit_insurance_calculation     dic ON dic.account_id = a.account_id
ORDER BY a.account_number;

-- KYC status
SELECT
  p.individual_name_given || ' ' || p.individual_name_family AS party_name,
  k.verification_status,
  k.risk_rating,
  k.cip_verification_method
FROM party p
JOIN kyc_cip_verification k ON k.party_id = p.party_id
ORDER BY party_name;

-- Trust beneficiaries
SELECT
  fa.document_name,
  p.individual_name_given || ' ' || p.individual_name_family AS beneficiary_name,
  fb.distribution_percentage
FROM fiduciary_arrangement fa
JOIN fiduciary_beneficiary fb ON fb.fiduciary_id = fa.fiduciary_id
JOIN party p ON p.party_id = fb.beneficiary_party_id
ORDER BY fb.distribution_sequence;
