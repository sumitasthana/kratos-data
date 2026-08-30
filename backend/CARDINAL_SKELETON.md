# Cardinal skeleton: what runs today

This is the walking skeleton. It proves the architecture end to end with the
smallest slice that exercises every part of the machine. It is not the credit
card simulator yet, and that is the point: the expensive, uncertain parts
(event sourcing, lag, determinism, the reject/regenerate loop) are answered
here for the price of a handful of fields.

## Run it

```bash
cd backend
pip install -r requirements.txt

# validate specs without generating
PYTHONPATH=src python -m cardinal.cli validate --spec specs/portfolio.yaml

# smoke portfolio: 1000 accounts x 24 cycles, deterministic, ~8s
PYTHONPATH=src python -m cardinal.cli generate --spec specs/portfolio.yaml --out data

# prove the one domain does work: turn it off, watch limits stop changing
PYTHONPATH=src python -m cardinal.cli generate --spec specs/portfolio.yaml --ablate --out data_ablated

# tests
python -m pytest tests -q
```

## What the skeleton proves

- **Deterministic.** Same seed, same content hash, on any machine. The manifest
  records the hash. (`test_determinism.py`)
- **Event-sourced.** Tables are projections of the event log. Replay the events
  and they match the stored `account_cycle` table to the cent.
  (`test_reconciliation.py`) This is the most valuable test in the suite.
- **Lag breaks the cycle.** The limit -> utilisation -> score -> limit loop is
  declared in the specs. The DAG builder proves it is acyclic once unrolled,
  and a spec that forgets a lag fails at build time. (`test_cycle_detection.py`)
- **Domains are wired, not decorative.** Ablate the line-increase handler and
  no limit ever changes. (`test_ablation.py`)
- **Reject and regenerate is real.** A hard `utilization <= 1.05` bound
  occasionally trips; the account regenerates with a fresh stream. The manifest
  reports the rejection rate.

## The three sockets everything plugs into

Defined in `src/cardinal/spec.py`:

- `Distribution` — add a family in `dist.py`, nothing else changes.
- `EventHandler` — add a domain in `domains.py`, register it, nothing else
  changes. `LineIncreaseHandler` is the worked example.
- `Invariant` — add a checker in `invariants.py`.

The rule that keeps scope contained: **nothing gets built unless it plugs into
one of these three.** If it does not fit, it is either not needed yet, or it is
a deliberate change to the harness itself.

## What is deliberately fake

- **Economics.** Spend and payment each cycle are simple draws from field
  specs, not calibrated billing. Real average-daily-balance interest, grace
  periods and minimum payments are Tier 1. The manifest marks every run
  `speculative: true`.
- **Invariant expressions.** The YAML carries human-readable `expr` strings.
  The runner maps invariant *ids* to hand-written checkers. A general
  expression evaluator is deferred until a real invariant needs one.
- **Eligibility grammar.** `predicate.py` handles `var OP literal` combined with
  AND. That covers every gate in the skeleton. Richer grammar when a gate needs
  it.

## Next, in order

1. **Decide the horizon (24 vs 36 cycles) and the macro path.** Both feed the
   emitter's partitioning, so settle them before Tier 1.
2. **Tier 1: real billing.** Replace the placeholder economics with
   average-daily-balance interest, grace-period logic (path-dependent on last
   cycle's payment), and the minimum-payment formula. Add origination so
   declines exist. This is the first output a bank analyst would believe.
3. **Wire `mypy --strict` and `ruff` into CI**, plus an import-linter contract
   so `engine` can never import an `agents` layer.
```
