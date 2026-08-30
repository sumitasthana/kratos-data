# Cardinal — status and next steps

_Last updated: 2026-08-30._

Plain-language record of what is built, what is deliberately simplified, and what comes next.

## What Cardinal does today

You open **Cardinal Studio**, describe in plain English the credit-card data you need, and
have a short conversation. The app proposes a plan, you confirm, and it produces:

- a **design graph** (the fields and how they depend on each other),
- a **runnable spec** (download as a `.zip` the engine can load), and
- a **data sample** with portfolio KPIs (revolve rate, utilisation, interest, delinquency).

The whole loop works end to end on live Claude (via Amazon Bedrock).

## What is built

**1. Deterministic engine (skeleton).** Seeded NumPy/SciPy. `spec` (YAML models + loader),
`dag` (unroll + cycle-detect + topological order), `dist` (distribution families), `rng`
(one stream per entity, so results are reproducible), `money` (Decimal), `invariants`,
`emit`, `cli`. One placeholder domain (credit-line increase) and tests (determinism,
reconciliation, cycle-detection, ablation).

**2. The ontology "brain".** A stored map of credit-card billing and the law behind it.
`agents/ontology/core.ttl` is the hand-authored vocabulary; `billing.ttl` is generated
from `billing_ontology.xlsx` by `build_ontology.py` (Excel is the source of truth, edit it,
never the `.ttl`). `ontology_service.py` loads it, runs an OWL 2 RL reasoner (owlrl, no Java)
and SHACL checks (pyshacl). This is where correctness and "what the law requires" live.

**3. Cardinal Studio (two agents + a contract).**
- **Interviewer** (`interviewer.py`, LangGraph, Claude via Bedrock): a real conversation.
  It reads what you say, proposes a concrete plan, and on your confirmation hands off a
  structured **contract** (`contract.py`).
- **Builder** (`builder.py`, deterministic, no LLM): takes the contract, uses the ontology to
  add whatever the law requires, closes over dependencies, validates through the engine's own
  loader, and **reports every field it added and why** (no "magic" additions).
- `spec_export.py` turns the design into a runnable engine spec bundle and validates it.
- FastAPI (`main.py`) and the React studio (chat + Graph / Spec / Data tabs) wire it together.

**4. The shared cycle loop + billing (the generation loop).**
- `cycle.py` is the **shared counter**: one generic per-account monthly loop that runs a list
  of domain modules. Adding a domain later is one more module; the loop never changes.
- `billing.py` is the first module: correct balance recurrence, average-daily-balance interest
  **gated by grace** (path-dependent on last month's pay-in-full), fees, minimum payment,
  payment archetypes, and spend capped at available credit. Verified deterministic, and the
  books balance to the cent.
- Studio's **Generate sample** button runs it and shows KPIs + a data table.

## Honest limitations (not bugs, known simplifications)

- **Demo parameters, not calibrated.** Billing distribution params in `billing.py` `DEFAULTS`
  are plausible demo values, not fitted to a published reference. The Data tab says so.
- **One blended balance.** Cash advances share the purchase balance for now; the
  "cash advances get no grace" refinement (Option B) is deferred.
- **Delinquency is a simplified missed-payment signal**, not a real Collections model.
- **Sample preview capped at 100 accounts** for speed; the downloaded spec carries the full size.
- **Two loops exist.** The new shared-counter loop (`cycle.py`) is the go-forward path; the
  legacy skeleton `engine.py generate()` (placeholder economics + its golden tests) is
  untouched and will be migrated onto the shared counter later.
- **Python 3.14 + langchain** prints a harmless pydantic-v1 warning.
- **GitHub repo is still named `kratos-data`.** Rename it on GitHub, then update the git remote.

## Next steps (roughly in order)

1. **Calibrate billing params** against a published reference (replace the demo defaults).
2. **Add the next domain as a new recipe** on the shared counter: Payments, then Collections
   (real days-past-due and charge-off, which unlocks honest delinquency KPIs).
3. **Full-size generate + download of the data** (not just the spec): stream per account,
   write partitioned Parquet.
4. **Migrate the legacy skeleton `generate()` onto the shared counter**, so there is one loop.
5. **Expand the ontology beyond billing** (origination, account setup) so the interview covers
   more of a real portfolio.
6. **Option B**: split purchase vs cash-advance balances (cash-advance-no-grace).
7. **Hardening**: session/spec persistence across restart, tests for the new agent and engine
   paths, and pin a Python for the agents environment if langchain friction appears.
