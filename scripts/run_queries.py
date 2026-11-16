#!/usr/bin/env python3
"""
Task 1 - Step 4: run the planned questions Q1-Q6 against Neo4j and save the results.

  results/qN_neo4j.csv   Cypher result
  results/qN_pandas.csv  independent pandas answer (run answers_pandas.py first)
  results/comparison.md  MATCH / DIFF for every question
"""
from __future__ import annotations

import pandas as pd

from kgconfig import NEO4J_DATABASE, QUERIES, RESULTS, get_driver


def _cell(v) -> str:
    """Comparable text form: lists sorted, numbers rounded, empty values as ''."""
    if isinstance(v, list):
        return "|".join(sorted(map(str, v)))
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) in ("", "nan", "None", "<NA>"):
        return ""
    try:
        return f"{round(float(v), 3):g}"
    except (TypeError, ValueError):
        return str(v)


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.apply(lambda col: col.map(_cell))
    return df.sort_values(list(df.columns)).reset_index(drop=True)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    report = ["# Q1-Q6: Cypher vs pandas", ""]
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        for path in sorted(QUERIES.glob("q*.cypher")):
            name = path.stem.split("_")[0]
            cypher = path.read_text().strip().rstrip(";")
            res = pd.DataFrame([r.data() for r in s.run(cypher)])
            res = res.apply(lambda col: col.map(
                lambda v: "|".join(sorted(map(str, v))) if isinstance(v, list) else v))
            res.to_csv(RESULTS / f"{name}_neo4j.csv", index=False)
            print(f"\n== {path.name} ==\n{res.to_string(index=False)}")

            pd_file = RESULTS / f"{name}_pandas.csv"
            if not pd_file.exists():
                report.append(f"- {name}: no pandas file (run answers_pandas.py)")
                continue
            ref = pd.read_csv(pd_file, keep_default_na=False)
            same = (list(ref.columns) == list(res.columns)
                    and normalise(ref).equals(normalise(res[ref.columns])))
            report.append(f"- {name}: {'MATCH' if same else 'DIFF'} ({len(res)} rows)")
            if not same:
                report += ["", "```", "Cypher:", res.to_string(index=False), "", "pandas:",
                           ref.to_string(index=False), "```", ""]
    driver.close()
    (RESULTS / "comparison.md").write_text("\n".join(report) + "\n")
    print("\n" + "\n".join(report))


if __name__ == "__main__":
    main()
