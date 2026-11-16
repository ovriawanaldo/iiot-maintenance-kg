#!/usr/bin/env python3
"""
Task 1 - Step 3: check the graph and report statistics.

Checks (each PASS/FAIL in reports/checks_report.md):
  C1 identifier uniqueness and presence per label
  C2 required properties present
  C3 every relationship connects existing nodes of allowed types; no unknown labels
  C4 cardinalities (each Event has one Machine and one SourceRecord, Failures have >= 1 mode ...)
  C5 provenance: every node and relationship has source and derivation
  C6 graph matches events.csv (event counts, mode links, KPI links, products, total downtime)
Also writes:
  reports/graph_stats.json               node and relationship counts, degree summaries
  reports/manual_verification_sample.csv 20 random events with graph values next to the raw
                                          AI4I values; fill the 'checked_by_hand' column yourself
"""
from __future__ import annotations

import json
import random
import sys

import pandas as pd

from kgconfig import (ALLOWED_LABELS, ALLOWED_RELS, EVENTS_CSV, NEO4J_DATABASE, NODE_KEYS, RAW_CSV,
                      REPORTS, REQUIRED_PROPS, get_driver, run)

SAMPLE_SIZE = 20
SEED = 2026


def check_all(s, ev: pd.DataFrame) -> list[tuple[str, bool, str]]:
    out = []

    # C1 uniqueness
    bad = []
    for label, key in NODE_KEYS.items():
        r = run(s, f"MATCH (n:{label}) RETURN count(n) AS n, count(n.{key}) AS present, "
                   f"count(DISTINCT n.{key}) AS distinct")[0]
        if not (r["n"] == r["present"] == r["distinct"]):
            bad.append(f"{label}.{key}: {r}")
    out.append(("C1 identifier uniqueness", not bad, "; ".join(bad) or "all keys present and unique"))

    # C2 required properties
    bad = []
    for label, props in REQUIRED_PROPS.items():
        for p in props:
            n = run(s, f"MATCH (n:{label}) WHERE n.{p} IS NULL RETURN count(n) AS c")[0]["c"]
            if n:
                bad.append(f"{n} {label} without {p}")
    out.append(("C2 required properties", not bad, "; ".join(bad) or "no missing required property"))

    # C3 relationship endpoints and labels
    triples = run(s, """MATCH (a)-[r]->(b)
                        RETURN labels(a) AS la, type(r) AS t, labels(b) AS lb, count(*) AS c""")
    bad = []
    for t in triples:
        ok = any(sa in t["la"] and rt == t["t"] and eb in t["lb"] for sa, rt, eb in ALLOWED_RELS)
        if not ok:
            bad.append(f"{t['la']}-[:{t['t']}]->{t['lb']} x{t['c']}")
    labels = {r["l"] for r in run(s, "MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l")}
    unknown = labels - ALLOWED_LABELS
    if unknown:
        bad.append(f"unknown labels {sorted(unknown)}")
    two = run(s, "MATCH (e:Event) WHERE (e:Failure AND e:ToolChange) OR (NOT e:Failure AND NOT e:ToolChange) "
                "RETURN count(e) AS c")[0]["c"]
    if two:
        bad.append(f"{two} Event nodes not exactly one of :Failure/:ToolChange")
    out.append(("C3 relationship types and endpoints", not bad, "; ".join(bad) or "all relationships allowed"))

    # C4 cardinalities
    rules = {
        "Event without exactly 1 OCCURRED_ON":
            "MATCH (e:Event) WHERE COUNT { (e)-[:OCCURRED_ON]->(:Machine) } <> 1 RETURN count(e) AS c",
        "Event without exactly 1 DERIVED_FROM":
            "MATCH (e:Event) WHERE COUNT { (e)-[:DERIVED_FROM]->(:SourceRecord) } <> 1 RETURN count(e) AS c",
        "Failure without a FailureMode":
            "MATCH (e:Failure) WHERE NOT (e)-[:HAS_FAILURE_MODE]->() RETURN count(e) AS c",
        "Failure without exactly 1 scrapped Product":
            "MATCH (e:Failure) WHERE COUNT { (e)-[:SCRAPPED]->(:Product) } <> 1 RETURN count(e) AS c",
        "ToolChange with a FailureMode or Product":
            "MATCH (e:ToolChange) WHERE (e)-[:HAS_FAILURE_MODE|SCRAPPED]->() RETURN count(e) AS c",
        "Product without exactly 1 variant":
            "MATCH (p:Product) WHERE COUNT { (p)-[:OF_VARIANT]->() } <> 1 RETURN count(p) AS c",
        "Machine without exactly 1 line and 1 model":
            "MATCH (m:Machine) WHERE COUNT { (m)-[:PART_OF]->() } <> 1 OR COUNT { (m)-[:INSTANCE_OF]->() } <> 1 "
            "RETURN count(m) AS c",
        "Isolated nodes (except unused FailureMode)":
            "MATCH (n) WHERE NOT (n)--() AND NOT n:FailureMode RETURN count(n) AS c",
    }
    bad = [f"{k}: {c}" for k, q in rules.items() if (c := run(s, q)[0]["c"])]
    out.append(("C4 cardinalities", not bad, "; ".join(bad) or "all cardinality rules hold"))

    # C5 provenance
    n_nodes = run(s, "MATCH (n) WHERE n.source IS NULL OR n.derivation IS NULL RETURN count(n) AS c")[0]["c"]
    n_rels = run(s, "MATCH ()-[r]->() WHERE r.source IS NULL OR r.derivation IS NULL RETURN count(r) AS c")[0]["c"]
    out.append(("C5 provenance on every node and relationship", n_nodes == n_rels == 0,
                f"{n_nodes} nodes and {n_rels} relationships without source/derivation"))

    # C6 graph vs events.csv
    modes = ev["failure_modes"].str.split("|").explode()
    expected = {
        "Failure": int((ev.event_type == "FAILURE").sum()),
        "ToolChange": int((ev.event_type == "TOOL_CHANGE").sum()),
        "HAS_FAILURE_MODE": int((modes != "").sum()),
        "AFFECTS_KPI": int(ev["kpi_affected"].str.split("|").str.len().sum()),
        "Product": ev.loc[ev.event_type == "FAILURE", "product_id"].nunique(),
        "SourceRecord": ev["source_udi"].nunique(),
        "total downtime_min": int(ev["downtime_min"].sum()),
    }
    actual = {
        "Failure": run(s, "MATCH (e:Failure) RETURN count(e) AS c")[0]["c"],
        "ToolChange": run(s, "MATCH (e:ToolChange) RETURN count(e) AS c")[0]["c"],
        "HAS_FAILURE_MODE": run(s, "MATCH ()-[r:HAS_FAILURE_MODE]->() RETURN count(r) AS c")[0]["c"],
        "AFFECTS_KPI": run(s, "MATCH ()-[r:AFFECTS_KPI]->() RETURN count(r) AS c")[0]["c"],
        "Product": run(s, "MATCH (p:Product) RETURN count(p) AS c")[0]["c"],
        "SourceRecord": run(s, "MATCH (n:SourceRecord) RETURN count(n) AS c")[0]["c"],
        "total downtime_min": run(s, "MATCH (e:Event) RETURN sum(e.downtime_min) AS c")[0]["c"],
    }
    diff = {k: (expected[k], actual[k]) for k in expected if expected[k] != actual[k]}
    out.append(("C6 graph matches events.csv", not diff,
                f"differences (csv, graph): {diff}" if diff else f"all equal: {expected}"))
    return out


def stats(s) -> dict:
    nodes = run(s, "MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS count ORDER BY l")
    rels = run(s, "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY type")
    per_machine = run(s, """MATCH (m:Machine)<-[:OCCURRED_ON]-(e)
                            RETURN m.machine_id AS machine, count(e) AS events ORDER BY machine""")
    per_mode = run(s, """MATCH (f:FailureMode) OPTIONAL MATCH (f)<-[:HAS_FAILURE_MODE]-(e)
                         RETURN f.code AS mode, count(e) AS events ORDER BY mode""")
    total_n = run(s, "MATCH (n) RETURN count(n) AS c")[0]["c"]
    total_r = run(s, "MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    return {"total_nodes": total_n, "total_relationships": total_r, "nodes_by_label": nodes,
            "relationships_by_type": rels, "events_per_machine": per_machine, "events_per_failure_mode": per_mode}


def manual_sample(s) -> pd.DataFrame:
    ids = [r["id"] for r in run(s, "MATCH (e:Event) RETURN e.event_id AS id ORDER BY id")]
    pick = sorted(random.Random(SEED).sample(ids, min(SAMPLE_SIZE, len(ids))))
    g = pd.DataFrame(run(s, """
        UNWIND $ids AS id
        MATCH (e:Event {event_id: id})-[:DERIVED_FROM]->(src:SourceRecord),
              (e)-[:OCCURRED_ON]->(m:Machine)-[:PART_OF]->(l:ProductionLine)
        OPTIONAL MATCH (e)-[:HAS_FAILURE_MODE]->(f:FailureMode)
        WITH e, src, m, l, collect(f.code) AS modes
        OPTIONAL MATCH (e)-[:SCRAPPED]->(p:Product)-[:OF_VARIANT]->(v:ProductVariant)
        RETURN e.event_id AS event_id, src.udi AS udi, src.row AS csv_row, m.machine_id AS machine,
               l.line_id AS line, e.event_type AS event_type, modes AS graph_modes,
               p.product_id AS graph_product, v.code AS graph_variant, e.rpm AS graph_rpm,
               e.torque_nm AS graph_torque, e.tool_wear_min AS graph_tool_wear
        """, ids=pick))
    g["graph_modes"] = g["graph_modes"].map(lambda x: "|".join(sorted(x)))
    if RAW_CSV.exists():
        raw = pd.read_csv(RAW_CSV)
        raw = raw.rename(columns={"UDI": "udi", "Product ID": "src_product", "Type": "src_variant",
                                  "Rotational speed [rpm]": "src_rpm", "Torque [Nm]": "src_torque",
                                  "Tool wear [min]": "src_tool_wear", "Machine failure": "src_machine_failure"})
        raw["src_modes"] = raw[["HDF", "OSF", "PWF", "RNF", "TWF"]].apply(
            lambda r: "|".join(k for k, v in r.items() if v == 1), axis=1)
        keep = ["udi", "src_product", "src_variant", "src_rpm", "src_torque", "src_tool_wear",
                "src_machine_failure", "src_modes"]
        g = g.merge(raw[keep], on="udi", how="left")
    g["checked_by_hand"] = ""   # write OK / WRONG after opening the AI4I row yourself
    g["note"] = ""
    return g


def main() -> None:
    ev = pd.read_csv(EVENTS_CSV, keep_default_na=False)
    REPORTS.mkdir(exist_ok=True)
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        results = check_all(s, ev)
        st = stats(s)
        sample = manual_sample(s)
    driver.close()

    prev = REPORTS / "graph_stats.json"
    rerun_note = ""
    if prev.exists():
        old = json.loads(prev.read_text())
        rerun_note = ("unchanged since previous check" if old["total_nodes"] == st["total_nodes"]
                      and old["total_relationships"] == st["total_relationships"]
                      else f"CHANGED: {old['total_nodes']}/{old['total_relationships']} -> "
                           f"{st['total_nodes']}/{st['total_relationships']}")
    prev.write_text(json.dumps(st, indent=2, default=str))
    sample.to_csv(REPORTS / "manual_verification_sample.csv", index=False)

    lines = ["# Graph checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {n} | {'PASS' if ok else 'FAIL'} | {d} |" for n, ok, d in results]
    lines += ["", f"Total nodes: {st['total_nodes']}, relationships: {st['total_relationships']}"
              + (f" ({rerun_note})" if rerun_note else ""), "",
              "## Nodes by label", *[f"- {x['label']}: {x['count']}" for x in st["nodes_by_label"]], "",
              "## Relationships by type", *[f"- {x['type']}: {x['count']}" for x in st["relationships_by_type"]],
              "", f"Manual verification sample ({len(sample)} events): reports/manual_verification_sample.csv"]
    (REPORTS / "checks_report.md").write_text("\n".join(lines) + "\n")

    for n, ok, d in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {n}: {d}")
    print(f"[check_graph] {st['total_nodes']} nodes, {st['total_relationships']} relationships. "
          f"Report: reports/checks_report.md")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


if __name__ == "__main__":
    main()
