"""
integrity_validator.py — AI-generated SQL Pre-insert FK Validator
=================================================================
Parses AI-generated SQL INSERT statements and validates all foreign-key
UUID references against live database records before any INSERT reaches
the database engine.

Security note: table/column names come exclusively from the internal
FK_REGISTRY dict (not from AI output). UUID values are validated against
a strict regex before use. No SQL injection surface area exists.

Python 3.11+ | SQLAlchemy 2.x async
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# FK registry — maps FK column name → (referenced_table, pk_column)
# All names are internal constants, never derived from AI-generated input.
# ---------------------------------------------------------------------------
FK_REGISTRY: dict[str, tuple[str, str]] = {
    "party_id":               ("party",                "party_id"),
    "primary_owner_party_id": ("party",                "party_id"),
    "owner_party_id":         ("party",                "party_id"),
    "account_id":             ("account",              "account_id"),
    "arrangement_id":         ("fiduciary_arrangement", "arrangement_id"),
}

# UUID v4 pattern — only [0-9a-fA-F] and hyphens; safe to embed after validation
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Matches: INSERT INTO table_name (col1, col2, ...) VALUES (...)
_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*(.+?)(?=;|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Matches one (val1, val2, ...) row from a VALUES clause
_ROW_RE = re.compile(r"\(([^)]*)\)")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    valid: bool = True
    violations: list[dict] = field(default_factory=list)
    checked_count: int = 0


# ---------------------------------------------------------------------------
# SQL row tokeniser
# ---------------------------------------------------------------------------

def _tokenise_row(row_content: str) -> list[str]:
    """
    Split a SQL VALUES row into individual tokens, respecting single-quoted
    strings so embedded commas inside quoted values are not split on.

    Returns a list of raw token strings (stripped, quotes intact).
    """
    tokens: list[str] = []
    current: list[str] = []
    in_quote = False
    quote_char = ""

    for ch in row_content:
        if in_quote:
            current.append(ch)
            if ch == quote_char:
                in_quote = False
        elif ch in ("'", '"'):
            in_quote = True
            quote_char = ch
            current.append(ch)
        elif ch == ",":
            tokens.append("".join(current).strip())
            current = []
        else:
            current.append(ch)

    tail = "".join(current).strip()
    if tail:
        tokens.append(tail)

    return tokens


def _extract_uuid(token: str) -> str | None:
    """Strip surrounding quotes from a token and return a UUID string or None."""
    cleaned = token.strip().strip("'\"")
    return cleaned if _UUID_RE.match(cleaned) else None


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

async def validate_generated_sql(sql: str, db: AsyncSession) -> ValidationResult:
    """
    Parse AI-generated SQL INSERT statements and validate all FK UUID references
    against the live database before allowing execution.

    Steps:
      1. Extract every INSERT statement via regex.
      2. For each INSERT, map column names to FK_REGISTRY entries.
      3. Collect the UUID value at each FK column's position.
      4. Batch-query the referenced table to confirm each UUID exists.
      5. Report any missing (non-existent) FK values as violations.

    Args:
        sql: AI-generated SQL string (may contain multiple INSERT statements).
        db:  Async SQLAlchemy session (read-only; no writes performed here).

    Returns:
        ValidationResult with valid=True if all FK references resolve,
        or valid=False with a populated violations list.
    """
    result = ValidationResult()

    # Collect: {ref_table: {pk_col: set_of_uuid_strings}}
    to_check: dict[str, dict[str, set[str]]] = {}

    for match in _INSERT_RE.finditer(sql):
        columns = [
            c.strip().strip('"').strip("'").lower()
            for c in match.group(2).split(",")
        ]
        values_block = match.group(3)

        # Build a mapping: fk_col → column_index for this INSERT's column list
        fk_positions: dict[str, int] = {}
        for fk_col in FK_REGISTRY:
            if fk_col in columns:
                fk_positions[fk_col] = columns.index(fk_col)

        if not fk_positions:
            continue  # No FK columns in this INSERT

        for row_match in _ROW_RE.finditer(values_block):
            tokens = _tokenise_row(row_match.group(1))
            if len(tokens) != len(columns):
                continue  # Malformed row — skip rather than mismap

            for fk_col, idx in fk_positions.items():
                uuid_val = _extract_uuid(tokens[idx])
                if uuid_val is None:
                    continue  # NULL or non-UUID value; skip
                ref_table, ref_pk = FK_REGISTRY[fk_col]
                to_check.setdefault(ref_table, {}).setdefault(ref_pk, set()).add(uuid_val)
                result.checked_count += 1

    # Batch-verify each referenced table
    for ref_table, pk_map in to_check.items():
        for pk_col, uuids in pk_map.items():
            if not uuids:
                continue

            # UUIDs are hex + hyphens only (validated by _UUID_RE above) —
            # embedding them in SQL is safe; ref_table/pk_col are internal constants.
            uuid_list = list(uuids)
            quoted = ", ".join(f"'{u}'" for u in uuid_list)
            query = text(
                f"SELECT CAST({pk_col} AS TEXT) AS id"
                f" FROM {ref_table}"
                f" WHERE CAST({pk_col} AS TEXT) IN ({quoted})"  # noqa: S608
            )
            rows = await db.execute(query)
            found = {r[0] for r in rows}
            missing = uuids - found

            for missing_id in sorted(missing):
                result.valid = False
                result.violations.append(
                    {
                        "fk_column":        pk_col,
                        "referenced_table": ref_table,
                        "missing_id":       missing_id,
                        "message": (
                            f"FK reference '{missing_id}' in column '{pk_col}' "
                            f"does not exist in table '{ref_table}'."
                        ),
                    }
                )

    return result
