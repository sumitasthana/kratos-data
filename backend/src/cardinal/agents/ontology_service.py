"""Ontology service: the deterministic brain the Builder agent sits on top of.

Loads core.ttl + billing.ttl, runs the OWL 2 RL reasoner (owlrl, no JVM), and
exposes the operations the Builder needs:
  - cached_ontology(): load + reason once, reuse read-only
  - apply_answer(design, field_ids): record chosen fields (A-Box growth)
  - emit_spec_yaml / design_elements: turn a design into Cardinal YAML / a graph
  - validate_design(graph): SHACL design-coherence check (pyshacl)

Run directly (`python ontology_service.py`) for the reasoning + validation self-test.
"""
from __future__ import annotations
import os
import yaml
from rdflib import Graph, Namespace, RDF, URIRef
from owlrl import DeductiveClosure, OWLRL_Semantics
from pyshacl import validate

SKOS_PREF = URIRef("http://www.w3.org/2004/02/skos/core#prefLabel")

HERE = os.path.dirname(os.path.abspath(__file__))
ONTO = os.path.join(HERE, "ontology")
CARD = Namespace("https://cardinal.dev/onto#")
BILL = Namespace("https://cardinal.dev/onto/billing#")


def load_ontology(reason: bool = True) -> Graph:
    g = Graph()
    g.parse(os.path.join(ONTO, "core.ttl"), format="turtle")
    g.parse(os.path.join(ONTO, "billing.ttl"), format="turtle")
    if reason:
        DeductiveClosure(OWLRL_Semantics).expand(g)
    return g


_REASONED_CACHE: Graph | None = None


def cached_ontology() -> Graph:
    """Load + reason once, reuse read-only across sessions (design graphs stay separate)."""
    global _REASONED_CACHE
    if _REASONED_CACHE is None:
        _REASONED_CACHE = load_ontology(reason=True)
    return _REASONED_CACHE


def new_design(name: str = "design_1") -> Graph:
    d = Graph()
    d.bind("card", CARD)
    d.bind("bill", BILL)
    URIRef(BILL[name])  # design node id
    d.add((BILL[name], RDF.type, CARD.Design))
    return d


def apply_answer(design: Graph, name: str, field_ids: list[str]) -> None:
    """Record that the user's design includes these fields (A-Box growth)."""
    for fid in field_ids:
        design.add((BILL[name], CARD.includesField, BILL[fid]))


def validate_design(data: Graph) -> tuple[bool, str]:
    conforms, _, text = validate(data, shacl_graph=data, inference="none", advanced=True)
    return conforms, text


def local(uri) -> str:
    return str(uri).split("#")[-1] if uri is not None else None


def included_fields(design: Graph, name: str = "design_1") -> list[str]:
    return sorted(local(o) for o in design.objects(BILL[name], CARD.includesField))


def emit_spec_yaml(onto: Graph, design: Graph, name: str = "design_1") -> str:
    """Turn the chosen fields (the A-Box) into a Cardinal spec YAML fragment.
    This is the payoff: the conversation becomes runnable generation config."""
    chosen = set(included_fields(design, name))
    spec: dict = {"fields": {}}
    for fid in sorted(chosen):
        uri = BILL[fid]
        entry: dict = {
            "grain": local(onto.value(uri, CARD.onGrain)),
            "dtype": str(onto.value(uri, CARD.dtype) or "decimal"),
        }
        if onto.value(uri, CARD.derived):
            entry["formula"] = str(onto.value(uri, CARD.formula))
        else:
            dist = onto.value(uri, CARD.distFamily)
            if dist is not None:
                entry["dist"] = {"family": local(dist)}  # TODO map to Cardinal family name
        # dependencies among chosen fields become depends_on entries
        deps = []
        for dep in onto.subjects(CARD.target, uri):
            src = onto.value(dep, CARD.source)
            if src is not None and local(src) in chosen:
                deps.append({
                    "field": local(src),
                    "lag": int(onto.value(dep, CARD.lag) or 0),
                    "mechanism": local(onto.value(dep, CARD.mechanism)),
                })
        if deps:
            entry["depends_on"] = sorted(deps, key=lambda d: d["field"])
        spec["fields"][fid] = entry
    return yaml.safe_dump(spec, sort_keys=False, width=100)


def design_elements(onto: Graph, design: Graph, name: str = "design_1") -> list[dict]:
    """Cytoscape elements for the current design: chosen fields + edges between them."""
    chosen = set(included_fields(design, name))
    els: list[dict] = []
    for fid in sorted(chosen):
        uri = BILL[fid]
        derived = bool(onto.value(uri, CARD.derived))
        els.append({"data": {
            "id": fid,
            "label": str(onto.value(uri, SKOS_PREF) or fid),
            "kind": "derived" if derived else "entered",
            "priority": local(onto.value(uri, CARD.priority)),
        }})
    for fid in sorted(chosen):
        uri = BILL[fid]
        for dep in onto.subjects(CARD.target, uri):
            src = onto.value(dep, CARD.source)
            if src is not None and local(src) in chosen:
                lag = int(onto.value(dep, CARD.lag) or 0)
                mech = local(onto.value(dep, CARD.mechanism))
                els.append({"data": {
                    "id": f"{local(src)}__{fid}",
                    "source": local(src), "target": fid,
                    "lag": lag, "mechanism": mech,
                    "label": f"lag {lag}" if lag else (mech or ""),
                }})
    return els


# --------------------------- self-test ---------------------------

def demo() -> None:
    print("=" * 68)
    print("REASONING (owlrl, OWL 2 RL, no JVM)")
    onto = load_ontology(reason=True)
    print(f"  triples after reasoning: {len(onto)}")
    # the reasoner's real work: transitive dependency closure that was never asserted
    inferred = (BILL.f_interest_charged, CARD.transitivelyDependsOn, BILL.f_payments)
    print(f"  inferred 'interest transitively depends on payments'? {inferred in onto}")

    print()
    print("SHACL DESIGN CHECK (pyshacl)")
    ok, _ = validate_design(load_ontology(reason=False))
    print(f"  ontology conforms? {ok}")
    bad = load_ontology(reason=False)
    bad.add((BILL.f_broken, RDF.type, CARD.DerivedField))  # derived, no formula
    ok2, text = validate_design(bad)
    print(f"  after adding a derived field with no formula, conforms? {ok2}")
    if not ok2:
        line = [l for l in text.splitlines() if "must declare a formula" in l]
        print(f"  caught: {line[0].strip() if line else 'violation reported'}")
    print("=" * 68)


if __name__ == "__main__":
    demo()
