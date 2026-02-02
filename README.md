# Kratos Data - Atomic Deposit System

## Overview

This repository contains a **highly normalized, atomic data model** for retail bank deposit systems with full **FDIC Part 370 compliance**. The schema is designed to ensure accurate deposit insurance determination and regulatory recordkeeping for financial institutions.

## Purpose

The Atomic Deposit System provides a comprehensive PostgreSQL database schema that:

- **Ensures regulatory compliance** with FDIC Part 370 (Recordkeeping for Timely Deposit Insurance Determination) and Part 330 (Deposit Insurance Coverage)
- **Maximizes data atomicity** - each column represents a single, irreducible fact with no composite data
- **Supports complex ownership structures** including individual, joint, trust, escrow, and government accounts
- **Provides full audit trails** with created/modified timestamps and user tracking
- **Enables accurate deposit insurance calculations** for diverse account types and ownership scenarios

## Key Features

### 🏦 Comprehensive Account Management
- Multi-party ownership (individual, joint, corporate, government)
- Diverse account types (savings, checking, money market, CDs, IRAs, trusts, escrow)
- Complex fiduciary arrangements and beneficiary tracking
- Account features (sweep accounts, POD/TOD designations, overdraft protection)

### 📊 Regulatory Compliance
- **FDIC Part 370**: Ownership Right & Capacity (ORC) classification with 24+ distinct types
- **FDIC Part 330**: Deposit insurance coverage rules (up to $250,000 per depositor per category)
- **FinCEN CIP**: Customer Identification Program (31 U.S.C. § 5318) compliance
- **KYC/AML**: Know Your Customer and Anti-Money Laundering verification tracking

### 🔐 Security & Controls
- Full audit logging of all data changes
- KYC/CIP verification status tracking
- Regulatory classification and control mappings
- Frozen account and legal hold support

### 💰 Financial Operations
- Transaction recording with full traceability
- Daily account balance snapshots
- Interest calculation support (simple, compound, various frequencies)
- Official items tracking (cashier's checks, money orders, etc.)
- GL control account reconciliation
- Automated deposit insurance calculations

## Database Schema

The schema consists of **14 core tables** organized into logical groups:

### Party & Customer Management
- **`party`** - Single source of truth for all parties (individuals, organizations, government entities)

### Account Management
- **`account`** - Core deposit account records
- **`account_ownership`** - Multi-party ownership and succession scenarios
- **`account_regulatory_classification`** - FDIC Part 370 ORC classifications
- **`account_feature`** - Account features (sweeps, POD/TOD, overdraft protection)

### Fiduciary & Trust Management
- **`fiduciary_arrangement`** - Trust agreements and escrow accounts
- **`fiduciary_beneficiary`** - Beneficiary tracking with distribution rules

### Transactions & Balances
- **`transaction`** - All account transactions
- **`daily_account_balance`** - Daily balance snapshots for reporting
- **`official_items`** - Cashier's checks, money orders, etc.

### Compliance & Controls
- **`kyc_cip_verification`** - Customer identification verification
- **`deposit_insurance_calculation`** - FDIC coverage calculations
- **`gl_deposit_control_account`** - General ledger reconciliation
- **`audit_log`** - Full audit trail of all changes

### Enumeration Types
The schema defines **24+ enumeration types** for data integrity:
- Party types and statuses
- Account types and statuses
- Ownership Right & Capacity (ORC) codes
- Interest calculation methods
- Transaction types
- KYC verification statuses
- And many more...

## File Structure

```
kratos-data/
├── 01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql    # PostgreSQL DDL script (1,219 lines)
│                                        # Creates all tables, enums, constraints,
│                                        # indexes, and triggers
│
├── 02_DATA_DICTIONARY.txt              # Comprehensive data dictionary (1,881 lines)
│                                        # Documents all tables, columns, enums,
│                                        # regulatory mappings, and control points
│
└── README.md                            # This file
```

## Prerequisites

- **PostgreSQL 14+** (uses advanced features like enumerations, CHECK constraints, triggers)
- Basic understanding of deposit banking operations
- Familiarity with FDIC deposit insurance rules (helpful but not required)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sumitasthana/kratos-data.git
   cd kratos-data
   ```

2. **Create a PostgreSQL database:**
   ```bash
   createdb atomic_deposit_system
   ```

3. **Execute the DDL script:**
   ```bash
   psql -d atomic_deposit_system -f 01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql
   ```

4. **Verify installation:**
   ```sql
   -- Connect to the database
   psql -d atomic_deposit_system
   
   -- List all tables
   \dt
   
   -- List all enumerations
   \dT+
   
   -- View party table structure
   \d party
   ```

## Usage Examples

### Create a Party (Individual Customer)
```sql
INSERT INTO party (
    party_type, party_status, first_name, last_name, 
    date_of_birth, ssn_last_4, created_by
) VALUES (
    'Individual', 'Active', 'John', 'Doe',
    '1980-05-15', '1234', 'system_admin'
);
```

### Create a Savings Account
```sql
INSERT INTO account (
    account_number, account_name, account_type, account_status,
    interest_rate_percent, currency_code, created_by
) VALUES (
    'SAV-001-2024', 'John Doe - Savings', 'Savings', 'Active',
    2.50, 'USD', 'system_admin'
);
```

### Link Party to Account (Single Owner)
```sql
INSERT INTO account_ownership (
    account_id, party_id, ownership_percent, 
    is_primary_owner, created_by
) VALUES (
    1, 1, 100.00, TRUE, 'system_admin'
);
```

### Classify for FDIC Insurance (Individual Account)
```sql
INSERT INTO account_regulatory_classification (
    account_id, orc_code, created_by
) VALUES (
    1, 'Single Account (ORC 01)', 'system_admin'
);
```

For more complex examples (joint accounts, trusts, beneficiaries), refer to the **02_DATA_DICTIONARY.txt** file, Section 7: Common Queries.

## Regulatory Compliance

### FDIC Part 370 - Recordkeeping Requirements
The schema captures all data elements required by **FDIC Part 370** for timely deposit insurance determination:
- Complete depositor information (Part 370 § 370.3)
- Ownership categories and rights (Part 370 Appendix A - 24 ORC codes)
- Account balance and interest calculations
- Fiduciary relationships and beneficiary designations

### FDIC Part 330 - Deposit Insurance Coverage
Supports accurate insurance calculations for:
- **Individual accounts**: $250,000 per depositor
- **Joint accounts**: $250,000 per co-owner
- **Revocable trusts**: $250,000 per beneficiary (up to 5 beneficiaries)
- **Retirement accounts**: $250,000 per depositor (separate from other categories)
- **Government accounts**: Varies by statute
- **Employee benefit plan accounts**: $250,000 per participant

### FinCEN Customer Identification Program (CIP)
Includes KYC/CIP verification tracking per **31 U.S.C. § 5318**:
- Identity verification status and methods
- Document types and expiration dates
- Verification dates and responsible parties

## Data Principles

1. **Maximum Atomicity**: Each column contains a single, indivisible fact (no composite data)
2. **No Redundancy**: Features and derived attributes built via views, not stored
3. **Full Audit Trail**: All tables include created_date, created_by, modified_date, modified_by
4. **Regulatory Traceability**: Explicit mappings to Part 370, Part 330, FinCEN requirements
5. **Data Integrity**: Extensive use of CHECK constraints, foreign keys, and enumerations

## Documentation

- **`01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql`**: Complete schema definition with inline comments explaining design decisions
- **`02_DATA_DICTIONARY.txt`**: Comprehensive reference including:
  - All enumeration types and their regulatory context
  - Table-by-table documentation
  - Column definitions and validation rules
  - Regulatory mappings (FDIC Part 370/330, FinCEN)
  - Control mappings for risk management
  - Common query examples
  - Appendices with additional guidance

## Contributing

Contributions are welcome! When proposing changes:

1. Maintain maximum data atomicity (no composite columns)
2. Include audit trail columns on all new tables
3. Document regulatory rationale for new data elements
4. Add corresponding entries to the data dictionary
5. Ensure compliance with FDIC Part 370/330 requirements
6. Test with realistic banking scenarios

## Design Rationale

This schema was designed by a risk & controls expert to address common challenges in deposit systems:

- **Problem**: Traditional deposit systems often combine multiple facts in single columns (e.g., "account holder name" mixing first, middle, last names)
- **Solution**: Atomic design with separate columns for each fact

- **Problem**: Deposit insurance calculations fail during bank failures due to incomplete ownership data
- **Solution**: Complete ORC classification and ownership tracking per FDIC Part 370

- **Problem**: Compliance teams struggle to produce regulatory reports
- **Solution**: Explicit regulatory mappings and pre-calculated insurance coverage

- **Problem**: Audit trails are incomplete or inconsistent
- **Solution**: Mandatory audit columns on every table with trigger-based tracking

## License

This project is provided as-is for educational and reference purposes. Please ensure compliance with all applicable banking regulations and consult with legal counsel before using in production.

## Author

**Risk & Controls Expert**  
Version 1.0  
Created: 2026-02-02

## Acknowledgments

- FDIC Part 370: Recordkeeping for Timely Deposit Insurance Determination
- FDIC Part 330: Deposit Insurance Coverage Rules
- FinCEN Customer Identification Program (31 U.S.C. § 5318)
- PostgreSQL Community for excellent database features

---

**Note**: This is a data model repository. For application code that uses this schema, please refer to the main Kratos application repository.
