#!/usr/bin/env python3
"""
Save the Task 1 graph as plain files (no APOC needed), so it can be compared with Task 2:
  graph_export/task1_nodes.csv          labels, stable id, all properties (JSON)
  graph_export/task1_relationships.csv  start id, type, end id, properties (JSON)
Each node is written as '<Label>:<key value>' so the files read the same on any machine.
"""
from __future__ import annotations

import json

import pandas as pd

from kgconfig import EXPORT, NEO4J_DATABASE, NODE_KEYS, get_driver


def key_expr(v: str) -> str:
    """Cypher expression giving '<Label>:<id>' for node variable v."""
    return "CASE " + " ".join(f"WHEN {v}:{lab} THEN '{lab}:' + toString({v}.{key})"
                              for lab, key in NODE_KEYS.items()) + " END"


def main() -> None:
    EXPORT.mkdir(exist_ok=True)
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        nodes = [r.data() for r in s.run(
            f"MATCH (n) RETURN {key_expr('n')} AS id, labels(n) AS labels, properties(n) AS props ORDER BY id")]
        rels = [r.data() for r in s.run(
            f"MATCH (a)-[r]->(b) WITH r, {key_expr('a')} AS start_id, {key_expr('b')} AS end_id "
            f"RETURN start_id, type(r) AS type, end_id, properties(r) AS props ORDER BY start_id, type, end_id")]
    driver.close()
    for row in nodes + rels:
        row["props"] = json.dumps(row["props"], default=str, sort_keys=True)
    for row in nodes:
        row["labels"] = "|".join(sorted(row["labels"]))
    pd.DataFrame(nodes).to_csv(EXPORT / "task1_nodes.csv", index=False)
    pd.DataFrame(rels).to_csv(EXPORT / "task1_relationships.csv", index=False)
    print(f"[export_graph] {len(nodes)} nodes, {len(rels)} relationships -> {EXPORT}")


if __name__ == "__main__":
    main()
