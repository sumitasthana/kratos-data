-- ============================================================================
-- ATOMIC DEPOSIT SYSTEM — AUDIT TRIGGER
-- Task 5: Generic row-level audit trigger applied to 5 tables
-- PostgreSQL 14+ | Requires hstore extension
-- ============================================================================
-- Regulatory: FDIC Part 370 § 370.3; 12 U.S.C. § 1831p-1 (management report)
--
-- Tables audited:
--   party, account, account_regulatory_classification,
--   deposit_insurance_calculation, kyc_cip_verification
--
-- Captures: table_name, primary_key_value, column_name, old_value, new_value,
--           change_type (INSERT/UPDATE/DELETE), changed_by, changed_date
--
-- changed_by is read from the session variable app.current_user.
-- Application must execute:
--   SET LOCAL app.current_user = 'alice.smith@bank.com';
-- inside each transaction before any DML.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0. Prerequisites
-- ---------------------------------------------------------------------------

-- hstore is needed for column-level change diffing
CREATE EXTENSION IF NOT EXISTS hstore;

-- ---------------------------------------------------------------------------
-- 1. change_type_enum
-- ---------------------------------------------------------------------------
-- NOTE: The original DDL contained an inline ENUM('INSERT','UPDATE','DELETE')
-- which is MySQL syntax, not valid PostgreSQL.  This block creates the proper
-- PostgreSQL enum type and patches the audit_log column.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type WHERE typname = 'change_type_enum'
  ) THEN
    CREATE TYPE change_type_enum AS ENUM ('INSERT', 'UPDATE', 'DELETE');
  END IF;
END
$$;

-- Patch audit_log.change_type to use the proper enum type.
-- Safe to run multiple times (ALTER is idempotent with the USING cast).
DO $$
BEGIN
  -- Only patch if the column is not already of type change_type_enum
  IF EXISTS (
    SELECT 1
    FROM   information_schema.columns
    WHERE  table_name   = 'audit_log'
      AND  column_name  = 'change_type'
      AND  udt_name    != 'change_type_enum'
  ) THEN
    ALTER TABLE audit_log
      ALTER COLUMN change_type TYPE change_type_enum
        USING change_type::change_type_enum;
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. Audit trigger function
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_audit_log_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
/*
  Generic audit trigger function.

  Behaviour:
    INSERT  → logs every column in NEW with old_value = NULL.
    UPDATE  → logs only columns that changed (hstore diff on NEW vs OLD).
    DELETE  → logs every column in OLD with new_value = NULL.

  changed_by is read from the session variable app.current_user.
  Set it in application code:
    SET LOCAL app.current_user = 'username@bank.com';

  Regulatory: FDIC Part 370 § 370.3 — complete audit trail required for
  timely deposit insurance determination.
*/
DECLARE
  v_changed_by  VARCHAR(50);
  v_pk_value    VARCHAR(100);
  v_pk_col      TEXT;
  v_col         TEXT;
  v_old_val     TEXT;
  v_new_val     TEXT;
  v_new_hstore  hstore;
  v_old_hstore  hstore;
  v_diff_hstore hstore;
BEGIN
  -- Read calling user from session variable; fall back to current DB role
  v_changed_by := COALESCE(
    NULLIF(current_setting('app.current_user', TRUE), ''),
    current_user
  );

  -- Identify the primary key column for this table
  -- (Assumes a single UUID PK named <tablename>_id or 'party_id', etc.)
  SELECT kcu.column_name
    INTO v_pk_col
    FROM information_schema.table_constraints       tc
    JOIN information_schema.key_column_usage        kcu
      ON kcu.constraint_name = tc.constraint_name
     AND kcu.table_schema    = tc.table_schema
    WHERE tc.table_name       = TG_TABLE_NAME
      AND tc.constraint_type  = 'PRIMARY KEY'
    LIMIT 1;

  -- ── INSERT ────────────────────────────────────────────────────────────────
  IF TG_OP = 'INSERT' THEN
    v_new_hstore := hstore(NEW);
    v_pk_value   := v_new_hstore -> v_pk_col;

    FOR v_col IN SELECT key FROM each(v_new_hstore) ORDER BY 1 LOOP
      v_new_val := v_new_hstore -> v_col;

      INSERT INTO audit_log (
        table_name, primary_key_value, column_name,
        old_value, new_value, change_type,
        changed_by, changed_date
      ) VALUES (
        TG_TABLE_NAME, v_pk_value, v_col,
        NULL, v_new_val, 'INSERT',
        v_changed_by, CURRENT_TIMESTAMP
      );
    END LOOP;

    RETURN NEW;

  -- ── UPDATE ────────────────────────────────────────────────────────────────
  ELSIF TG_OP = 'UPDATE' THEN
    v_new_hstore  := hstore(NEW);
    v_old_hstore  := hstore(OLD);
    v_pk_value    := v_new_hstore -> v_pk_col;

    -- Diff: only keys that have changed values
    v_diff_hstore := v_new_hstore - v_old_hstore;

    -- Also include keys that existed in OLD but not in NEW (rare with static schema)
    -- hstore subtraction already handles this for value changes.

    FOR v_col IN SELECT key FROM each(v_diff_hstore) ORDER BY 1 LOOP
      v_old_val := v_old_hstore -> v_col;
      v_new_val := v_new_hstore -> v_col;

      -- Skip audit-metadata columns to prevent recursive log bloat
      CONTINUE WHEN v_col IN ('modified_date', 'modified_by', 'created_date', 'created_by');

      INSERT INTO audit_log (
        table_name, primary_key_value, column_name,
        old_value, new_value, change_type,
        changed_by, changed_date
      ) VALUES (
        TG_TABLE_NAME, v_pk_value, v_col,
        v_old_val, v_new_val, 'UPDATE',
        v_changed_by, CURRENT_TIMESTAMP
      );
    END LOOP;

    RETURN NEW;

  -- ── DELETE ────────────────────────────────────────────────────────────────
  ELSIF TG_OP = 'DELETE' THEN
    v_old_hstore := hstore(OLD);
    v_pk_value   := v_old_hstore -> v_pk_col;

    FOR v_col IN SELECT key FROM each(v_old_hstore) ORDER BY 1 LOOP
      v_old_val := v_old_hstore -> v_col;

      INSERT INTO audit_log (
        table_name, primary_key_value, column_name,
        old_value, new_value, change_type,
        changed_by, changed_date
      ) VALUES (
        TG_TABLE_NAME, v_pk_value, v_col,
        v_old_val, NULL, 'DELETE',
        v_changed_by, CURRENT_TIMESTAMP
      );
    END LOOP;

    RETURN OLD;

  END IF;

  RETURN NULL;
END;
$$;

COMMENT ON FUNCTION fn_audit_log_trigger() IS
  'Generic row-level audit trigger that captures all column changes into audit_log.
   Regulatory: FDIC Part 370 § 370.3 — full audit trail for deposit insurance determination.
   Uses hstore diff to capture only modified columns on UPDATE (performance-efficient).
   Set session variable app.current_user before DML to attribute changes correctly.';

-- ---------------------------------------------------------------------------
-- 3. Drop existing triggers (idempotent re-run safety)
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_audit_party                         ON party;
DROP TRIGGER IF EXISTS trg_audit_account                       ON account;
DROP TRIGGER IF EXISTS trg_audit_account_reg_classification    ON account_regulatory_classification;
DROP TRIGGER IF EXISTS trg_audit_deposit_insurance_calculation ON deposit_insurance_calculation;
DROP TRIGGER IF EXISTS trg_audit_kyc_cip_verification          ON kyc_cip_verification;

-- ---------------------------------------------------------------------------
-- 4. Apply trigger to the 5 required tables
-- ---------------------------------------------------------------------------
-- AFTER trigger: runs after the row change so NEW / OLD are fully populated.
-- FOR EACH ROW: column-level granularity required for FDIC audit trail.

-- 4a. PARTY — most critical: customer identity (FinCEN CIP 31 U.S.C. § 5318)
CREATE TRIGGER trg_audit_party
  AFTER INSERT OR UPDATE OR DELETE ON party
  FOR EACH ROW EXECUTE FUNCTION fn_audit_log_trigger();

COMMENT ON TRIGGER trg_audit_party ON party IS
  'Audit all party record changes. Per FinCEN CIP (31 U.S.C. § 5318): '
  'customer identity data must have a full modification history.';

-- 4b. ACCOUNT — core deposit account (FDIC Part 370 § 370.4)
CREATE TRIGGER trg_audit_account
  AFTER INSERT OR UPDATE OR DELETE ON account
  FOR EACH ROW EXECUTE FUNCTION fn_audit_log_trigger();

COMMENT ON TRIGGER trg_audit_account ON account IS
  'Audit all account record changes. Per FDIC Part 370 § 370.4: '
  'account data must be current and auditable.';

-- 4c. ACCOUNT_REGULATORY_CLASSIFICATION — ORC code (FDIC Part 370 Appendix A)
CREATE TRIGGER trg_audit_account_reg_classification
  AFTER INSERT OR UPDATE OR DELETE ON account_regulatory_classification
  FOR EACH ROW EXECUTE FUNCTION fn_audit_log_trigger();

COMMENT ON TRIGGER trg_audit_account_reg_classification ON account_regulatory_classification IS
  'Audit all ORC classification changes. Per FDIC Part 370 § 370.3(b): '
  'ORC assignment and changes must be traceable.';

-- 4d. DEPOSIT_INSURANCE_CALCULATION — coverage calc (FDIC Part 330)
CREATE TRIGGER trg_audit_deposit_insurance_calculation
  AFTER INSERT OR UPDATE OR DELETE ON deposit_insurance_calculation
  FOR EACH ROW EXECUTE FUNCTION fn_audit_log_trigger();

COMMENT ON TRIGGER trg_audit_deposit_insurance_calculation ON deposit_insurance_calculation IS
  'Audit all insurance calculation records. Per FDIC Part 330 § 330.1: '
  'calculation methodology and results must be auditable.';

-- 4e. KYC_CIP_VERIFICATION — customer identification (FinCEN CIP)
CREATE TRIGGER trg_audit_kyc_cip_verification
  AFTER INSERT OR UPDATE OR DELETE ON kyc_cip_verification
  FOR EACH ROW EXECUTE FUNCTION fn_audit_log_trigger();

COMMENT ON TRIGGER trg_audit_kyc_cip_verification ON kyc_cip_verification IS
  'Audit all KYC/CIP verification changes. Per FinCEN CIP (31 U.S.C. § 5318): '
  'identity verification history must be retained.';

-- ---------------------------------------------------------------------------
-- 5. Helper: application session variable setter
-- ---------------------------------------------------------------------------
-- Call this from the application layer at the start of every transaction:
--   SELECT set_audit_user('alice.smith@bank.com');

CREATE OR REPLACE FUNCTION set_audit_user(p_user_id VARCHAR(50))
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  -- LOCAL sets the variable only for the current transaction.
  PERFORM set_config('app.current_user', p_user_id, TRUE);
END;
$$;

COMMENT ON FUNCTION set_audit_user(VARCHAR) IS
  'Sets the app.current_user session variable used by fn_audit_log_trigger() '
  'to attribute row changes to the correct application user. '
  'Call at the start of each transaction: SELECT set_audit_user(''username'');';

-- ---------------------------------------------------------------------------
-- 6. Verification query
-- ---------------------------------------------------------------------------

-- Confirm triggers are registered on the 5 tables:
SELECT
    event_object_table  AS table_name,
    trigger_name,
    event_manipulation  AS event,
    action_timing       AS timing
FROM information_schema.triggers
WHERE trigger_name LIKE 'trg_audit_%'
ORDER BY event_object_table, event_manipulation;

-- ---------------------------------------------------------------------------
-- 7. Usage example
-- ---------------------------------------------------------------------------
/*
  -- In application code / SQL:
  BEGIN;
    SELECT set_audit_user('john.doe@kratos.bank');

    UPDATE party
       SET individual_name_family = 'Smith-Jones',
           modified_by            = 'john.doe@kratos.bank',
           modified_date          = CURRENT_TIMESTAMP
     WHERE party_id = '...';
  COMMIT;

  -- Check audit log:
  SELECT table_name, primary_key_value, column_name,
         old_value, new_value, change_type, changed_by, changed_date
  FROM   audit_log
  WHERE  table_name       = 'party'
    AND  primary_key_value = '...'
  ORDER  BY changed_date DESC;
*/
