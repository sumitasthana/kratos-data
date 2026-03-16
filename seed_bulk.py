#!/usr/bin/env python3
"""
seed_bulk.py  —  Bulk seed script for Atomic Deposit System
All column names verified against DDL v1.0
"""

import asyncio, random, uuid, os, re
from datetime import date, timedelta

import asyncpg
from dotenv import load_dotenv

load_dotenv()  # reads .env from project root

# ── CONFIG — reads from .env (falls back to defaults if not set) ─────────────
def _parse_db_url(url: str):
    """Extract host/port/user/pass/dbname from a DATABASE_URL."""
    # postgresql+asyncpg://user:pass@host:port/dbname
    m = re.match(
        r"[^:]+://(?P<user>[^:]+):(?P<pass>[^@]+)@(?P<host>[^:/]+):?(?P<port>\d*)/(?P<db>.+)",
        url,
    )
    if not m:
        return None
    from urllib.parse import unquote
    return (
        m.group("host"),
        int(m.group("port") or 5432),
        m.group("user"),
        unquote(m.group("pass")),   # decode %40 -> @ etc.
        m.group("db"),
    )

_db_url    = os.getenv("DATABASE_URL", "")
_db_parsed = _parse_db_url(_db_url) if _db_url else None

DB_HOST    = _db_parsed[0] if _db_parsed else "localhost"
DB_PORT    = _db_parsed[1] if _db_parsed else 5432
DB_USER    = _db_parsed[2] if _db_parsed else "postgres"
DB_PASS    = _db_parsed[3] if _db_parsed else "CHANGE_ME"
DB_NAME    = _db_parsed[4] if _db_parsed else "atomic_deposit_system"
BATCH      = 500
N_PARTIES  = 4000
N_ACCOUNTS = 6000
FDIC_LIMIT = 250_000.0
TODAY      = date.today()
# ─────────────────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda",
    "William","Barbara","David","Susan","Richard","Jessica","Joseph","Sarah",
    "Thomas","Karen","Charles","Lisa","Christopher","Nancy","Daniel","Betty",
    "Matthew","Margaret","Anthony","Sandra","Mark","Ashley","Donald","Dorothy",
    "Steven","Kimberly","Paul","Emily","Andrew","Donna","Joshua","Michelle",
    "Kenneth","Carol","Kevin","Amanda","Brian","Melissa","George","Deborah",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas",
    "Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White",
    "Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker","Young",
    "Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
]
CITIES_STATES = [
    ("New York","NY"),("Los Angeles","CA"),("Chicago","IL"),("Houston","TX"),
    ("Phoenix","AZ"),("Philadelphia","PA"),("San Antonio","TX"),("San Diego","CA"),
    ("Dallas","TX"),("San Jose","CA"),("Austin","TX"),("Jacksonville","FL"),
    ("Fort Worth","TX"),("Columbus","OH"),("Charlotte","NC"),("Boston","MA"),
    ("Seattle","WA"),("Denver","CO"),("Nashville","TN"),("Atlanta","GA"),
    ("Miami","FL"),("Portland","OR"),("Las Vegas","NV"),("Minneapolis","MN"),
]
ACCOUNT_TYPES = [
    "Savings","Checking","Money Market","Certificate of Deposit",
    "Individual Retirement Account","Trust Account","Business Account","Escrow Account"
]
ORC_MAP = {
    "Savings":                       ["Single","Joint_JTWROS","Joint_TenancyInCommon","POD_PayableOnDeath"],
    "Checking":                      ["Single","Joint_JTWROS","Business_SoleProprietor","POD_PayableOnDeath"],
    "Money Market":                  ["Single","Joint_JTWROS","Business_LLC"],
    "Certificate of Deposit":        ["Single","IRA_Traditional","IRA_Roth"],
    "Individual Retirement Account": ["IRA_Traditional","IRA_Roth","IRA_SEP","IRA_SIMPLE"],
    "Trust Account":                 ["Trust_Revocable","Trust_Irrevocable","Trust_Charitable"],
    "Business Account":              ["Business_Corporation","Business_Partnership","Business_LLC","Business_SoleProprietor"],
    "Escrow Account":                ["Escrow_Agent","FiduciaryOther"],
}
CIP_METHODS   = [
    "DocumentReview_DriversLicense","DocumentReview_Passport","DocumentReview_GovernmentID",
    "ThirdPartyMatch_Equifax","ThirdPartyMatch_Experian","BiometricMatch_FacialRecognition"
]
RISK_RATINGS  = ["Low","Medium","High","Critical"]
PROG_TYPES    = ["CIP","KYC","Enhanced","Simplified"]

def rand_date(start=1940, end=2000):
    s = date(start,1,1); e = date(end,12,31)
    return s + timedelta(days=random.randint(0,(e-s).days))

def rand_ssn():
    return f"{random.randint(100,999):03d}{random.randint(10,99):02d}{random.randint(1000,9999):04d}"

def rand_balance(atype):
    ranges = {
        "Savings":(500,150_000),"Checking":(100,50_000),
        "Money Market":(2_000,500_000),"Certificate of Deposit":(1_000,300_000),
        "Individual Retirement Account":(5_000,500_000),"Trust Account":(10_000,800_000),
        "Business Account":(1_000,1_000_000),"Escrow Account":(500,200_000),
    }
    lo,hi = ranges.get(atype,(500,100_000))
    return round(random.uniform(lo,hi),2)

def orc_flags(orc):
    return (
        orc.startswith("Joint_"),
        orc.startswith("IRA_"),
        orc.startswith("Keogh_"),
        orc.startswith("Trust_"),
        orc.startswith("Government_"),
        orc.startswith("Business_"),
        orc == "POD_PayableOnDeath",
        orc == "TOD_TransferOnDeath",
    )

async def flush(conn, sql, rows):
    if rows:
        await conn.executemany(sql, rows)
        rows.clear()

async def main():
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME
    )
    print("✓ Connected.")

    # ── 1. PARTIES ────────────────────────────────────────────────────────────
    print(f"\nInserting {N_PARTIES} parties...")
    PARTY_SQL = """
        INSERT INTO party (
            party_id, party_type, party_status,
            individual_name_given, individual_name_middle, individual_name_family,
            individual_date_of_birth, individual_ssn,
            organization_legal_name, organization_tax_id,
            address_street_line1, address_city, address_state_province,
            address_postal_code, address_country, address_is_usa,
            phone_number_primary, email_primary,
            created_by, modified_by
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
        ON CONFLICT DO NOTHING"""

    party_ids, rows = [], []
    for i in range(N_PARTIES):
        pid = uuid.uuid4()
        fn  = random.choice(FIRST_NAMES)
        ln  = random.choice(LAST_NAMES)
        city, state = random.choice(CITIES_STATES)
        party_ids.append(pid)
        rows.append((
            pid,"Individual","Active",
            fn,None,ln,rand_date(),rand_ssn(),
            None,None,
            f"{random.randint(100,9999)} {random.choice(['Main','Oak','Elm','Cedar'])} St",
            city,state,f"{random.randint(10000,99999)}","US",True,
            f"+1{random.randint(2000000000,9999999999)}",
            f"{fn.lower()}.{ln.lower()}{random.randint(1,999)}@email.com",
            "seed_bulk","seed_bulk"
        ))
        if len(rows)==BATCH:
            await conn.executemany(PARTY_SQL,rows); rows.clear()
            print(f"  ... {i+1} parties")
    await flush(conn, PARTY_SQL, rows)
    print(f"  ✓ {N_PARTIES} parties done.")

    # ── 2. KYC / CIP ─────────────────────────────────────────────────────────
    # Real PK:  verification_id
    # Required: verification_program_type, identity_verified, identity_verification_date,
    #           sanctions_screening_performed, pep_screening_performed,
    #           adverse_media_screening_performed, beneficial_owner_identified,
    #           verification_status, verification_status_date, created_by
    print("\nInserting KYC/CIP records...")
    KYC_SQL = """
        INSERT INTO kyc_cip_verification (
            verification_id, party_id, verification_program_type,
            cip_verification_method,
            identity_verified, identity_verification_date,
            sanctions_screening_performed, sanctions_screening_date,
            sanctions_screening_database, sanctions_screening_result,
            pep_screening_performed, pep_screening_date, pep_status,
            adverse_media_screening_performed, adverse_media_screening_date,
            beneficial_owner_identified,
            verification_status, verification_status_date,
            risk_rating, risk_rating_date,
            created_by
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
        ON CONFLICT DO NOTHING"""

    rows = []
    for pid in party_ids:
        vdate = TODAY - timedelta(days=random.randint(1,365))
        rows.append((
            uuid.uuid4(), pid,
            random.choice(PROG_TYPES),
            random.choice(CIP_METHODS),
            True, vdate,
            True, vdate, "OFAC",
            random.choice(["Clear","PossibleMatch"]),
            True, vdate,
            random.choice(["NotPEP","PEP","Unknown"]),
            True, vdate,
            False,
            random.choice(["Complete","Pending","Manual_Review"]), vdate,
            random.choice(RISK_RATINGS), vdate,
            "seed_bulk"
        ))
        if len(rows)==BATCH:
            await conn.executemany(KYC_SQL,rows); rows.clear()
    await flush(conn, KYC_SQL, rows)
    print(f"  ✓ {N_PARTIES} KYC/CIP records done.")

    # ── 3. ACCOUNTS ───────────────────────────────────────────────────────────
    # Real cols: account_open_date (NOT NULL), primary_owner_party_id (NOT NULL),
    #            interest_rate_percentage (not interest_rate_annual),
    #            current_balance_date (NOT NULL)
    # Removed:   ledger_balance, accrued_interest, pending_transactions,
    #            currency_code, is_interest_bearing (don't exist in DDL)
    print(f"\nInserting {N_ACCOUNTS} accounts...")
    ACCT_SQL = """
        INSERT INTO account (
            account_id, account_number, account_type, account_status,
            account_open_date, primary_owner_party_id,
            interest_rate_percentage,
            current_balance, current_balance_date,
            created_by, modified_by
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        ON CONFLICT DO NOTHING"""

    acct_ids, acct_types, acct_bal, acct_owner = [], [], {}, {}
    rows = []
    for i in range(N_ACCOUNTS):
        aid    = uuid.uuid4()
        at     = random.choice(ACCOUNT_TYPES)
        bal    = rand_balance(at)
        owner  = random.choice(party_ids)
        odate  = TODAY - timedelta(days=random.randint(30,3650))
        acct_ids.append(aid)
        acct_types.append(at)
        acct_bal[aid]   = bal
        acct_owner[aid] = owner
        rows.append((
            aid, f"ACC-{i+100001:06d}", at, "Active",
            odate, owner,
            round(random.uniform(0.01,4.5),4),
            bal, TODAY,
            "seed_bulk","seed_bulk"
        ))
        if len(rows)==BATCH:
            await conn.executemany(ACCT_SQL,rows); rows.clear()
            print(f"  ... {i+1} accounts")
    await flush(conn, ACCT_SQL, rows)
    print(f"  ✓ {N_ACCOUNTS} accounts done.")

    # ── 4. ACCOUNT OWNERSHIP ──────────────────────────────────────────────────
    # Real PK:   account_ownership_id  (not ownership_id)
    # Real FK:   owner_party_id        (not party_id)
    # Required:  ownership_verification_date (NOT NULL)
    # UNIQUE:    (account_id, owner_party_id)  ← must deduplicate!
    print("\nInserting ownership records...")
    OWN_SQL = """
        INSERT INTO account_ownership (
            account_ownership_id, account_id, owner_party_id,
            ownership_role, ownership_percentage_amount,
            ownership_effective_date, ownership_verification_date,
            ownership_verification_method,
            created_by
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT DO NOTHING"""

    rows = []
    seen_pairs = set()
    for aid in acct_ids:
        primary = acct_owner[aid]
        key = (str(aid), str(primary))
        if key not in seen_pairs:
            seen_pairs.add(key)
            rows.append((
                uuid.uuid4(), aid, primary,
                "PrimaryOwner", 100.0,
                TODAY, TODAY, "DocumentReview", "seed_bulk"
            ))
        if random.random() < 0.3:
            joint = random.choice(party_ids)
            key2  = (str(aid), str(joint))
            if key2 not in seen_pairs:
                seen_pairs.add(key2)
                rows.append((
                    uuid.uuid4(), aid, joint,
                    "JointOwner", 50.0,
                    TODAY, TODAY, "DocumentReview", "seed_bulk"
                ))
        if len(rows)>=BATCH:
            await conn.executemany(OWN_SQL,rows); rows.clear()
    await flush(conn, OWN_SQL, rows)
    print("  ✓ Ownership records done.")

    # ── 5. ORC CLASSIFICATION ─────────────────────────────────────────────────
    # Required: orc_verification_date (NOT NULL)
    # Added:    boolean flags (is_joint_ownership, is_ira, etc.)
    # account_id is UNIQUE — one classification per account
    print("\nInserting ORC classifications...")
    ORC_SQL = """
        INSERT INTO account_regulatory_classification (
            classification_id, account_id, orc_code,
            orc_insured_amount_per_owner, orc_insurance_category,
            orc_determination_date, orc_determination_method,
            orc_verification_date,
            is_joint_ownership, is_ira, is_keogh, is_trust,
            is_government, is_business, is_payable_on_death, is_transfer_on_death,
            created_by
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
        ON CONFLICT DO NOTHING"""

    classification_map = {}   # aid -> (cid, orc)
    rows = []
    for aid, atype in zip(acct_ids, acct_types):
        cid  = uuid.uuid4()
        orc  = random.choice(ORC_MAP.get(atype,["Single"]))
        flags = orc_flags(orc)
        classification_map[aid] = (cid, orc)
        rows.append((
            cid, aid, orc,
            FDIC_LIMIT, "Covered",
            TODAY, "AutomatedMatch", TODAY,
            *flags,
            "seed_bulk"
        ))
        if len(rows)>=BATCH:
            await conn.executemany(ORC_SQL,rows); rows.clear()
    await flush(conn, ORC_SQL, rows)
    print("  ✓ ORC classifications done.")

    # ── 6. DEPOSIT INSURANCE CALCULATION ─────────────────────────────────────
    # classification_id FK is REQUIRED (not orc_code)
    # Real cols: input_account_balance, input_accrued_interest, input_owner_count,
    #            input_orc, part_330_rules_version_date
    # No created_by column in this table
    print("\nInserting deposit insurance calculations...")
    INS_SQL = """
        INSERT INTO deposit_insurance_calculation (
            calculation_id, account_id, classification_id,
            calculation_scenario,
            input_account_balance, input_accrued_interest,
            input_owner_count, input_orc,
            part_330_rules_version_date, part_330_rules_smdia_amount,
            calculated_insured_amount, calculated_uninsured_amount,
            calculation_test_result
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        ON CONFLICT DO NOTHING"""

    rows = []
    for aid in acct_ids:
        cid, orc = classification_map[aid]
        bal   = acct_bal[aid]
        ins   = min(bal, FDIC_LIMIT)
        unins = max(0.0, bal - FDIC_LIMIT)
        rows.append((
            uuid.uuid4(), aid, cid,
            "Normal",
            round(bal,2), 0.0,
            1, orc,
            date(2024,1,1), FDIC_LIMIT,
            round(ins,2), round(unins,2),
            "Pass" if unins==0 else "Fail"
        ))
        if len(rows)>=BATCH:
            await conn.executemany(INS_SQL,rows); rows.clear()
    await flush(conn, INS_SQL, rows)
    print("  ✓ Insurance calculations done.")

    # ── 7. DAILY ACCOUNT BALANCE ──────────────────────────────────────────────
    # Real table: daily_account_balance  (NOT daily_balance_snapshot)
    # Real PK:    composite (account_id, balance_as_of_date)  — no UUID PK!
    # Real cols:  balance_opening_amount, balance_deposits_amount,
    #             balance_withdrawals_amount, balance_interest_amount,
    #             balance_fees_amount, balance_corrections_amount, balance_closing_amount
    print("\nInserting daily account balances (30 days × 1200 accounts)...")
    SNAP_SQL = """
        INSERT INTO daily_account_balance (
            account_id, balance_as_of_date,
            balance_opening_amount, balance_deposits_amount,
            balance_withdrawals_amount, balance_interest_amount,
            balance_fees_amount, balance_corrections_amount,
            balance_closing_amount,
            created_by
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT DO NOTHING"""

    rows = []
    for aid in random.sample(acct_ids, k=min(1200,len(acct_ids))):
        bal = acct_bal[aid]
        for d in range(30):
            snap = TODAY - timedelta(days=d)
            op   = round(bal * random.uniform(0.97,1.03),2)
            dep  = round(random.uniform(0,5000),2)
            wd   = round(random.uniform(0,3000),2)
            intr = round(random.uniform(0,50),2)
            fee  = round(random.uniform(0,25),2)
            cl   = round(op + dep - wd + intr - fee,2)
            rows.append((aid,snap,op,dep,wd,intr,fee,0.0,cl,"seed_bulk"))
            if len(rows)>=BATCH:
                await conn.executemany(SNAP_SQL,rows); rows.clear()
    await flush(conn, SNAP_SQL, rows)
    print("  ✓ Daily balances done.")

    # ── FINAL COUNTS ──────────────────────────────────────────────────────────
    counts = await conn.fetch("""
        SELECT 'party'                              t, COUNT(*) c FROM party              UNION ALL
        SELECT 'account',                              COUNT(*)   FROM account             UNION ALL
        SELECT 'kyc_cip_verification',                 COUNT(*)   FROM kyc_cip_verification UNION ALL
        SELECT 'account_ownership',                    COUNT(*)   FROM account_ownership   UNION ALL
        SELECT 'account_regulatory_classification',    COUNT(*)   FROM account_regulatory_classification UNION ALL
        SELECT 'deposit_insurance_calculation',        COUNT(*)   FROM deposit_insurance_calculation UNION ALL
        SELECT 'daily_account_balance',                COUNT(*)   FROM daily_account_balance
    """)
    print("\n── Final Row Counts ────────────────────────────────────────")
    total = 0
    for r in counts:
        print(f"  {r['t']:45s} {r['c']:>8,}")
        total += r['c']
    print(f"  {'─'*53}")
    print(f"  {'TOTAL':45s} {total:>8,}")
    print("────────────────────────────────────────────────────────────")
    await conn.close()
    print("\n✓ Seeding complete.")

if __name__ == "__main__":
    asyncio.run(main())
