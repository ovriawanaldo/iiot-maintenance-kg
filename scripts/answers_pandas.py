#!/usr/bin/env python3
"""
Independent check for Q1-Q6: compute the same answers with pandas directly from events.csv
(no graph). run_queries.py compares these files with the Cypher results.

Output: results/qN_pandas.csv (same columns as the Cypher queries).
"""
from __future__ import annotations

import pandas as pd

from kgconfig import EVENTS_CSV, RESULTS


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = pd.read_csv(EVENTS_CSV, keep_default_na=False)
    fail = ev[ev.event_type == "FAILURE"].copy()
    fm = fail.assign(mode=fail.failure_modes.str.split("|")).explode("mode")  # one row per (event, mode)
    return ev, fm


def q1(ev, fm):
    f = ev[ev.event_type == "FAILURE"]
    tot = f.groupby("line_id").agg(failures=("event_id", "count"), downtime_min=("downtime_min", "sum"))
    md = fm.groupby(["line_id", "mode"])["downtime_min"].sum().reset_index()
    md = md.sort_values(["line_id", "downtime_min", "mode"], ascending=[True, False, True])
    top = md.groupby("line_id").head(1).set_index("line_id")
    tot["top_mode"] = top["mode"]
    tot["top_mode_downtime_min"] = top["downtime_min"]
    return tot.reset_index().sort_values("downtime_min", ascending=False)


def q2(ev, fm):
    h = fm[fm["mode"] == "HDF"]
    return (h.groupby(["machine_id", "line_id"])
             .agg(hdf_events=("event_id", "nunique"), downtime_min=("downtime_min", "sum"),
                  max_temp_delta_k=("temp_delta_k", "max"), max_rpm=("rpm", "max"))
             .reset_index().sort_values(["hdf_events", "machine_id"], ascending=[False, True]))


def q3(ev, fm):
    o = fm[fm["mode"] == "OSF"]
    return (o.groupby(["product_type", "line_id"])["product_id"].nunique()
             .reset_index().rename(columns={"product_type": "variant", "product_id": "scrapped_products"})
             .sort_values(["variant", "line_id"]))


def q4(ev, fm):
    multi = ev[ev.failure_modes.str.contains(r"\|")].copy()
    multi["mode_combination"] = multi.failure_modes.map(lambda s: "+".join(sorted(s.split("|"))))
    return (multi.groupby("mode_combination")
                 .agg(events=("event_id", "nunique"),
                      machines=("machine_id", lambda s: "|".join(sorted(set(s)))))
                 .reset_index().sort_values(["events", "mode_combination"], ascending=[False, True]))


def q5(ev, fm):
    p = fm[fm["mode"] == "PWF"].copy()
    p["power_class"] = p["power_w"].map(lambda w: "HIGH" if w > 9000 else "LOW" if w < 3500 else "INSIDE_3500_9000")
    return (p.groupby(["power_class", "line_id", "product_type"])["event_id"].nunique().reset_index()
             .rename(columns={"product_type": "variant", "event_id": "events"})
             .sort_values(["power_class", "line_id", "variant"]))


def q6(ev, fm):
    tc = ev[ev.event_type == "TOOL_CHANGE"].copy()
    tc["tool_wear_before_min"] = pd.to_numeric(tc["tool_wear_before_min"])
    a = tc.groupby("machine_id").agg(tool_changes=("event_id", "count"),
                                     change_wear_min=("tool_wear_before_min", "min"),
                                     change_wear_max=("tool_wear_before_min", "max"))
    t = fm[fm["mode"] == "TWF"]
    b = t.groupby("machine_id").agg(twf_failures=("event_id", "nunique"),
                                    twf_wear_min=("tool_wear_min", "min"),
                                    twf_wear_max=("tool_wear_min", "max"))
    out = pd.DataFrame(index=sorted(ev.machine_id.unique())).join(a).join(b)
    out[["tool_changes", "twf_failures"]] = out[["tool_changes", "twf_failures"]].fillna(0).astype(int)
    return out.rename_axis("machine_id").reset_index()


QUESTIONS = {"q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5, "q6": q6}


def proposal_check(ev: pd.DataFrame, fm: pd.DataFrame, rejected_n: int | None) -> list[str]:
    """Compare with the numbers written in the approved proposal (V6, sections 02 and 03)."""
    f = ev[ev.event_type == "FAILURE"]
    line = f.groupby("line_id")["downtime_min"].agg(["sum", "count"])
    get = lambda s, k: int(s.get(k, 0))  # noqa: E731
    hdf = fm[fm["mode"] == "HDF"]
    osf = fm[fm["mode"] == "OSF"]
    pwf = fm[fm["mode"] == "PWF"]
    tc = ev[ev.event_type == "TOOL_CHANGE"].groupby("machine_id").size()
    twf = fm[fm["mode"] == "TWF"].groupby("machine_id").size()
    combos = q4(ev, fm).set_index("mode_combination")
    checks = [
        ("events total", 458, len(ev)),
        ("FAILURE events", 339, len(f)),
        ("TOOL_CHANGE events", 119, int((ev.event_type == "TOOL_CHANGE").sum())),
        ("UNSPECIFIED failures", 9, int((f.failure_modes == "UNSPECIFIED").sum())),
        ("rejected rows", 18, rejected_n),
        ("Q1 LINE-A downtime", 10505, get(line["sum"], "LINE-A")),
        ("Q1 LINE-A failures", 235, get(line["count"], "LINE-A")),
        ("Q1 LINE-B downtime", 4245, get(line["sum"], "LINE-B")),
        ("Q1 LINE-B failures", 104, get(line["count"], "LINE-B")),
        ("Q1 HDF downtime on LINE-A", 5220, int(hdf[hdf.line_id == "LINE-A"].downtime_min.sum())),
        ("Q2 machines with HDF", "CNC-02", "|".join(sorted(hdf.machine_id.unique()))),
        ("Q2 HDF events", 115, hdf.event_id.nunique()),
        ("Q3 OSF scrapped, variant L", 87, osf[osf.product_type == "L"].event_id.nunique()),
        ("Q3 OSF scrapped, total", 98, osf.event_id.nunique()),
        ("Q3 OSF L on LINE-A", 48, osf[(osf.product_type == "L") & (osf.line_id == "LINE-A")].event_id.nunique()),
        ("Q3 OSF variant M", 9, osf[osf.product_type == "M"].event_id.nunique()),
        ("Q3 OSF variant H", 2, osf[osf.product_type == "H"].event_id.nunique()),
        ("Q4 multi-mode events", 24, int(ev.failure_modes.str.contains(r"\|").sum())),
        ("Q4 events with exactly OSF+PWF", 11, int(combos["events"].get("OSF+PWF", 0))),
        ("Q4 events with HDF and another mode (all on CNC-02)", "9 / CNC-02",
         f"{int(combos.loc[combos.index.str.contains('HDF'), 'events'].sum())} / "
         + "|".join(sorted(set("|".join(combos.loc[combos.index.str.contains('HDF'), 'machines']).split("|"))))),
        ("Q5 PWF high (> 9000 W)", 64, int((pwf.power_w > 9000).sum())),
        ("Q5 PWF low (< 3500 W)", 31, int((pwf.power_w < 3500).sum())),
        ("Q6 tool changes CNC-01/02/03/04", "29/30/29/31",
         "/".join(str(int(tc.get(m, 0))) for m in ["CNC-01", "CNC-02", "CNC-03", "CNC-04"])),
        ("Q6 TWF CNC-01/02/03/04", "8/13/12/13",
         "/".join(str(int(twf.get(m, 0))) for m in ["CNC-01", "CNC-02", "CNC-03", "CNC-04"])),
    ]
    return [f"[{'OK  ' if str(exp) == str(got) else 'DIFF'}] {name}: proposal {exp} | data {got}"
            for name, exp, got in checks]


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    ev, fm = load()
    for name, fn in QUESTIONS.items():
        df = fn(ev, fm)
        df.to_csv(RESULTS / f"{name}_pandas.csv", index=False)
        print(f"\n== {name} (pandas, from events.csv) ==\n{df.to_string(index=False)}")
    multi = int(ev.failure_modes.str.contains(r"\|").sum())
    print(f"\nEvents with two or more failure modes: {multi}")

    rej = EVENTS_CSV.parent / "rejected_records.csv"
    rejected_n = len(pd.read_csv(rej)) if rej.exists() else None
    lines = proposal_check(ev, fm, rejected_n)
    (RESULTS / "proposal_numbers_check.txt").write_text("\n".join(lines) + "\n")
    print("\n== Numbers in the approved proposal vs this run ==")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
