"""Builder agent: turns a finalized Contract into a validated Cardinal spec.

Deterministic, no LLM. This is where accuracy lives:
  1. seed the design from the contract's behaviours,
  2. let the ontology pull in everything the law requires (obligations),
  3. close over dependencies so the spec is self-contained,
  4. SHACL-validate, emit YAML + a graph,
  5. report every field it added and why (transparency, no magic).
"""
from __future__ import annotations
from rdflib import URIRef

try:
    from .ontology_service import (
        cached_ontology, load_ontology, new_design, apply_answer, emit_spec_yaml,
        design_elements, validate_design, included_fields, local, SKOS_PREF, CARD, BILL,
    )
    from .contract import Contract
    from .spec_export import engine_spec_files, validate_spec_files
except ImportError:
    from ontology_service import (
        cached_ontology, load_ontology, new_design, apply_answer, emit_spec_yaml,
        design_elements, validate_design, included_fields, local, SKOS_PREF, CARD, BILL,
    )
    from contract import Contract
    from spec_export import engine_spec_files, validate_spec_files

DCT_SOURCE = URIRef("http://purl.org/dc/terms/source")

# contract behaviour -> the field(s) that seed it in the ontology
BEHAVIOR_SEEDS = {
    "grace_period": ["f_revolving_balance"],   # obligation then pulls the grace fields
    "fees": ["f_fees"],
    "cash_advances": ["f_cash_advance"],
    "minimum_payment": ["f_minimum_payment_due"],
}


class Builder:
    def __init__(self):
        # one SHACL pass on the field definitions at startup, not per build
        self._valid, _ = validate_design(load_ontology(reason=False))

    def _label(self, fid: str) -> str:
        return str(cached_ontology().value(BILL[fid], SKOS_PREF) or fid)

    def _human_list(self, ids) -> str:
        labels = [self._label(i).lower() for i in ids]
        if len(labels) == 1:
            return labels[0]
        return ", ".join(labels[:-1]) + " and " + labels[-1]

    def _satisfy_obligations(self, onto, design, name, assumptions):
        obligations = set(onto.subjects(CARD.triggeredByField, None))
        changed = True
        while changed:
            changed = False
            included = set(included_fields(design, name))
            for ob in obligations:
                trig = onto.value(ob, CARD.triggeredByField)
                if trig is None or local(trig) not in included:
                    continue
                reqs = [local(r) for r in onto.objects(ob, CARD.requiresField)]
                missing = [r for r in reqs if r not in included]
                if missing:
                    apply_answer(design, name, missing)
                    changed = True
                    label = str(onto.value(ob, SKOS_PREF) or local(ob))
                    src = onto.value(ob, DCT_SOURCE)
                    cite = f" ({src})" if src else ""
                    assumptions.append(
                        f"Added {self._human_list(missing)} because \"{label}\" is required{cite}.")

    def _close_dependencies(self, onto, design, name, assumptions):
        added = set()
        changed = True
        while changed:
            changed = False
            for fid in list(included_fields(design, name)):
                for src in onto.objects(BILL[fid], CARD.directlyDependsOn):
                    s = local(src)
                    if s not in included_fields(design, name):
                        apply_answer(design, name, [s])
                        added.add(s)
                        changed = True
        if added:
            assumptions.append(
                "Also pulled in the fields these are computed from: "
                + self._human_list(sorted(added)) + ".")

    def build(self, contract: Contract) -> dict:
        onto = cached_ontology()
        name = "build"
        design = new_design(name)
        assumptions: list[str] = []

        seeds: set[str] = set()
        for b in contract.behaviors:
            seeds.update(BEHAVIOR_SEEDS.get(b, []))
        if contract.revolver_mix in ("mostly_revolvers", "mixed") and "f_revolving_balance" not in seeds:
            seeds.add("f_revolving_balance")
            assumptions.append("Set accounts up to carry balances, since the portfolio has revolvers.")
        if not seeds:  # nothing chosen: give a minimal sensible starter
            seeds.add("f_revolving_balance")
            assumptions.append("Nothing specific was requested, so I started with a standard revolving portfolio.")

        apply_answer(design, name, sorted(seeds))
        self._satisfy_obligations(onto, design, name, assumptions)
        self._close_dependencies(onto, design, name, assumptions)

        fields = included_fields(design, name)
        spec_files = engine_spec_files(onto, design, contract, name)
        validation = validate_spec_files(spec_files)
        bundle_text = "\n".join(f"# ===== {rel} =====\n{text}" for rel, text in spec_files.items())
        return {
            "yaml": bundle_text,                 # full runnable bundle, shown on the Spec tab
            "graph": design_elements(onto, design, name),
            "assumptions": assumptions,
            "valid": self._valid,
            "fields": fields,
            "spec_files": spec_files,            # for the .zip download
            "validation": validation,            # engine load + DAG result
        }
