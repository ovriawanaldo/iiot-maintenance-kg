#!/usr/bin/env python3
"""
Task 1 - Step 2: load events.csv into Neo4j as the initial knowledge graph.

Idempotent: every node is MERGEd on its stable identifier (backed by a uniqueness
constraint) and every relationship is MERGEd between existing nodes, so running the
script again changes nothing. Use --reset to rebuild from an empty database.

Every node and relationship stores
  source     : where the fact comes from (file name or citation)
  derivation : stated (value in AI4I) | computed (arithmetic on AI4I values) | constructed (my rule)

Usage:
  export NEO4J_PASSWORD=...        # plus NEO4J_URI / NEO4J_USER if not default
  python scripts/load_graph.py --reset
  python scripts/load_graph.py --dry-run     # no database; prints what would be written
"""
from __future__ import annotations

import argparse

import pandas as pd

from kgconfig import EVENTS_CSV, MACHINES_CSV, NEO4J_DATABASE, QUERIES, get_driver, run

AI4I = "AI4I 2020 (Matzka 2020, DOI 10.24432/C5HS5C)"
EVENTS = "events.csv (scripts/build_events.py)"
ISO = "ISO 22400-2:2014"
BATCH = 500

# ---------------------------------------------------------------- reference nodes
FAILURE_MODES = [
    # code, name, rule as described in the AI4I documentation, derivation
    ("TWF", "Tool wear failure", "tool replaced or fails at a wear time between 200 and 240 min", "stated"),
    ("HDF", "Heat dissipation failure", "air-process temperature difference below 8.6 K and speed below 1380 rpm", "stated"),
    ("PWF", "Power failure", "process power below 3500 W or above 9000 W", "stated"),
    ("OSF", "Overstrain failure", "tool wear x torque above 11000 (L), 12000 (M), 13000 (H) min*Nm", "stated"),
    ("RNF", "Random failure", "0.1 % chance per process, independent of the process parameters", "stated"),
    ("UNSPECIFIED", "Unspecified failure", "Machine failure = 1 but no failure-mode flag set", "constructed"),
]
KPIS = [("Availability", "Availability", "share of planned busy time the machine actually runs"),
        ("Quality", "Quality ratio", "good quantity / produced quantity")]
VARIANTS = [("L", "Low quality variant", 0.5, 11000), ("M", "Medium quality variant", 0.3, 12000),
            ("H", "High quality variant", 0.2, 13000)]
MODEL_ID = "HAAS-VF2"
MACHINES_SRC = "machines.csv (scripts/build_events.py)"


def constraints() -> list[str]:
    text = (QUERIES / "00_constraints.cypher").read_text()
    text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
    return [c.strip() for c in text.split(";") if c.strip()]


def load_events(path=EVENTS_CSV) -> pd.DataFrame:
    ev = pd.read_csv(path, keep_default_na=False, dtype=str)
    for c in ["source_udi", "source_row", "downtime_min", "scrap_parts", "rpm", "power_w", "tool_wear_min"]:
        ev[c] = ev[c].astype(int)
    for c in ["air_temp_k", "process_temp_k", "temp_delta_k", "torque_nm"]:
        ev[c] = ev[c].astype(float)
    ev["planned"] = ev["planned"].map({"True": True, "False": False})
    return ev


def build_batches(ev: pd.DataFrame) -> dict[str, list[dict]]:
    """Turn events.csv into parameter lists, one list per Cypher statement."""
    b: dict[str, list[dict]] = {k: [] for k in
                                ["events", "occurred_on", "derived_from", "modes", "kpis", "scrapped"]}
    for r in ev.itertuples(index=False):
        props = {
            "event_type": r.event_type, "timestamp": r.timestamp.replace(" ", "T"),
            "planned": r.planned, "downtime_min": r.downtime_min, "scrap_parts": r.scrap_parts,
            "product_id": r.product_id, "air_temp_k": r.air_temp_k, "process_temp_k": r.process_temp_k,
            "temp_delta_k": r.temp_delta_k, "rpm": r.rpm, "torque_nm": r.torque_nm,
            "power_w": r.power_w, "tool_wear_min": r.tool_wear_min,
        }
        if r.tool_wear_before_min != "":
            props["tool_wear_before_min"] = int(r.tool_wear_before_min)
        b["events"].append({"event_id": r.event_id, "label": "Failure" if r.event_type == "FAILURE" else "ToolChange",
                            "props": props})
        b["occurred_on"].append({"event_id": r.event_id, "machine_id": r.machine_id})
        b["derived_from"].append({"event_id": r.event_id, "udi": r.source_udi,
                                  "file": r.source_file, "row": r.source_row})
        for code in filter(None, r.failure_modes.split("|")):
            b["modes"].append({"event_id": r.event_id, "code": code,
                               "derivation": "constructed" if code == "UNSPECIFIED" else "stated"})
        for kpi in r.kpi_affected.split("|"):
            b["kpis"].append({"event_id": r.event_id, "kpi_id": kpi,
                              "downtime_min": r.downtime_min if kpi == "Availability" else None,
                              "scrap_parts": r.scrap_parts if kpi == "Quality" else None})
        if r.event_type == "FAILURE":
            b["scrapped"].append({"event_id": r.event_id, "product_id": r.product_id,
                                  "variant": r.product_type})
    return b


STATEMENTS = {
    # Event nodes: two passes so the extra label can be set without APOC
    "events": """
        UNWIND $rows AS r
        MERGE (e:Event {event_id: r.event_id})
        SET e += r.props, e.timestamp = localdatetime(r.props.timestamp),
            e.source = $events_src, e.derivation = 'constructed',
            e.sensor_values_derivation = 'stated', e.computed_props = ['temp_delta_k', 'power_w']
        WITH e, r WHERE r.label = 'Failure'  SET e:Failure
        """,
    "events_tc": """
        UNWIND $rows AS r WITH r WHERE r.label = 'ToolChange'
        MATCH (e:Event {event_id: r.event_id}) SET e:ToolChange
        """,
    "occurred_on": """
        UNWIND $rows AS r
        MATCH (e:Event {event_id: r.event_id}), (m:Machine {machine_id: r.machine_id})
        MERGE (e)-[x:OCCURRED_ON]->(m)
        SET x.source = $events_src, x.derivation = 'constructed'
        """,
    "derived_from": """
        UNWIND $rows AS r
        MATCH (e:Event {event_id: r.event_id})
        MERGE (s:SourceRecord {udi: r.udi})
        SET s.file = r.file, s.row = r.row, s.source = $ai4i, s.derivation = 'stated'
        MERGE (e)-[x:DERIVED_FROM]->(s)
        SET x.source = $events_src, x.derivation = 'constructed'
        """,
    "modes": """
        UNWIND $rows AS r
        MATCH (e:Event {event_id: r.event_id}), (fm:FailureMode {code: r.code})
        MERGE (e)-[x:HAS_FAILURE_MODE]->(fm)
        SET x.source = $ai4i, x.derivation = r.derivation
        """,
    "kpis": """
        UNWIND $rows AS r
        MATCH (e:Event {event_id: r.event_id}), (k:KPI {kpi_id: r.kpi_id})
        MERGE (e)-[x:AFFECTS_KPI]->(k)
        SET x.downtime_min = r.downtime_min, x.scrap_parts = r.scrap_parts,
            x.source = $events_src, x.derivation = 'constructed'
        """,
    "scrapped": """
        UNWIND $rows AS r
        MATCH (e:Event {event_id: r.event_id}), (v:ProductVariant {code: r.variant})
        MERGE (p:Product {product_id: r.product_id})
        SET p.source = $ai4i, p.derivation = 'stated'
        MERGE (e)-[x:SCRAPPED]->(p)
        SET x.source = $events_src, x.derivation = 'constructed'
        MERGE (p)-[y:OF_VARIANT]->(v)
        SET y.source = $ai4i, y.derivation = 'stated'
        """,
}


def load_reference(session) -> None:
    machines = pd.read_csv(MACHINES_CSV)
    for model_name in machines["machine_model"].unique():   # one model: all mills are Haas VF-2
        run(session, """
            MERGE (mm:MachineModel {model_id: $id})
            SET mm.name = $name, mm.source = 'assumption stated in proposal section 03',
                mm.derivation = 'constructed'
            """, id=MODEL_ID, name=model_name)
    for line in sorted(machines["line_id"].unique()):
        run(session, "MERGE (l:ProductionLine {line_id: $id}) SET l.source = $s, l.derivation = 'constructed'",
            id=line, s=MACHINES_SRC)
    for r in machines.itertuples(index=False):
        run(session, """
            MATCH (l:ProductionLine {line_id: $line}), (mm:MachineModel {model_id: $model})
            MERGE (m:Machine {machine_id: $id})
            SET m.udi_from = $udi_from, m.udi_to = $udi_to, m.cycles = $cycles,
                m.source = $s, m.derivation = 'constructed'
            MERGE (m)-[a:PART_OF]->(l)          SET a.source = $s, a.derivation = 'constructed'
            MERGE (m)-[b:INSTANCE_OF]->(mm)     SET b.source = $s, b.derivation = 'constructed'
            """, id=r.machine_id, line=r.line_id, model=MODEL_ID, udi_from=int(r.udi_from),
            udi_to=int(r.udi_to), cycles=int(r.cycles), s=MACHINES_SRC)
    for code, name, rule, der in FAILURE_MODES:
        run(session, """MERGE (f:FailureMode {code: $code})
                        SET f.name = $name, f.ai4i_rule = $rule, f.source = $src, f.derivation = $der""",
            code=code, name=name, rule=rule, der=der, src=AI4I if der == "stated" else EVENTS)
    for kid, name, definition in KPIS:
        run(session, """MERGE (k:KPI {kpi_id: $id})
                        SET k.name = $name, k.definition = $d, k.source = $src, k.derivation = 'stated'""",
            id=kid, name=name, d=definition, src=ISO)
    for code, name, share, osf in VARIANTS:
        run(session, """MERGE (v:ProductVariant {code: $code})
                        SET v.name = $name, v.share_in_ai4i = $share, v.osf_threshold_min_nm = $osf,
                            v.source = $src, v.derivation = 'stated'""",
            code=code, name=name, share=share, osf=osf, src=AI4I)


def counts(session) -> dict:
    nodes = run(session, "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY l")
    rels = run(session, "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY t")
    return {"nodes": {x["l"]: x["c"] for x in nodes}, "relationships": {x["t"]: x["c"] for x in rels}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="delete all nodes before loading")
    ap.add_argument("--dry-run", action="store_true", help="do not connect; print batch sizes")
    args = ap.parse_args()

    ev = load_events()
    batches = build_batches(ev)
    if args.dry_run:
        for k, v in batches.items():
            print(f"[dry-run] {k:13s}: {len(v):5d} rows   e.g. {v[0] if v else '-'}")
        return

    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        if args.reset:
            run(s, "MATCH (n) DETACH DELETE n")
        for c in constraints():
            run(s, c)
        before = counts(s)
        load_reference(s)
        params = {"events_src": EVENTS, "ai4i": AI4I}
        for key, rows in [("events", batches["events"]), ("events_tc", batches["events"])] + \
                         [(k, batches[k]) for k in ["occurred_on", "derived_from", "modes", "kpis", "scrapped"]]:
            for i in range(0, len(rows), BATCH):
                run(s, STATEMENTS[key], rows=rows[i:i + BATCH], **params)
        after = counts(s)
    driver.close()

    print("[load_graph] nodes        :", after["nodes"])
    print("[load_graph] relationships:", after["relationships"])
    if before["nodes"] and before == after:
        print("[load_graph] repeated import: counts unchanged -> load is idempotent")
    elif before["nodes"]:
        print("[load_graph] WARNING counts changed on re-import:", before, "->", after)


if __name__ == "__main__":
    main()
