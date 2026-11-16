#!/usr/bin/env python3
"""
Task 1 - Step 1: build the constructed events dataset from AI4I 2020.

Input : data/raw/ai4i2020.csv  (Matzka 2020, UCI, DOI 10.24432/C5HS5C, CC BY 4.0)
Output: data/constructed/events.csv           one row per FAILURE or TOOL_CHANGE event
        data/constructed/machines.csv         the four constructed machines and their UDI blocks
        data/constructed/rejected_records.csv rows that do not fit the schema, with a reason

Construction rules (fixed in the proposal, section 03-B). The script is deterministic:
running it twice gives byte-identical files.

  machine_id / line_id : 2,500 consecutive UDIs = one machine.
                         UDI 1-2500 -> CNC-01, 2501-5000 -> CNC-02 (LINE-A)
                         UDI 5001-7500 -> CNC-03, 7501-10000 -> CNC-04 (LINE-B)
  timestamp            : per machine, replay from 2026-10-01 06:00, one row = one 5-minute cycle
  FAILURE event        : Machine failure = 1                          -> event_id EVT-<udi:05d>
  TOOL_CHANGE event    : tool wear lower than in the previous row of the same machine
                                                                       -> event_id TC-<udi:05d>
  failure_modes        : the AI4I flags set to 1 (TWF|HDF|PWF|OSF|RNF); none set -> UNSPECIFIED
  downtime_min         : TWF 25, HDF 45, PWF 60, OSF 35, RNF/UNSPECIFIED 15;
                         several modes -> the largest value; tool change -> 10
  kpi_affected         : FAILURE -> Availability|Quality ; TOOL_CHANGE -> Availability
  scrap_parts          : FAILURE -> 1 (the product of that cycle is scrapped); TOOL_CHANGE -> 0
  computed             : temp_delta_k = process - air temperature; power_w = torque * rpm * 2*pi/60

Rejected (written to rejected_records.csv, never loaded):
  missing value, non-numeric value, flag not 0/1, product type not L/M/H, duplicate UDI,
  UDI outside 1-10000, mode flag without machine_failure (a mode flag is 1 but Machine failure is 0)
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "data" / "raw" / "ai4i2020.csv"
DEFAULT_OUT = ROOT / "data" / "constructed"

# Original AI4I header -> snake_case name used everywhere else
AI4I_COLUMNS = {
    "UDI": "udi",
    "Product ID": "product_id",
    "Type": "product_type",
    "Air temperature [K]": "air_temp_k",
    "Process temperature [K]": "process_temp_k",
    "Rotational speed [rpm]": "rpm",
    "Torque [Nm]": "torque_nm",
    "Tool wear [min]": "tool_wear_min",
    "Machine failure": "machine_failure",
    "TWF": "TWF", "HDF": "HDF", "PWF": "PWF", "OSF": "OSF", "RNF": "RNF",
}
MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]
NUMERIC = ["udi", "air_temp_k", "process_temp_k", "rpm", "torque_nm", "tool_wear_min",
           "machine_failure"] + MODES
FLAGS = ["machine_failure"] + MODES

DOWNTIME_BY_MODE = {"TWF": 25, "HDF": 45, "PWF": 60, "OSF": 35, "RNF": 15, "UNSPECIFIED": 15}
TOOL_CHANGE_DOWNTIME = 10
ROWS_PER_MACHINE = 2500
MACHINES = [("CNC-01", "LINE-A"), ("CNC-02", "LINE-A"), ("CNC-03", "LINE-B"), ("CNC-04", "LINE-B")]
MACHINE_MODEL = "Haas VF-2 (40-taper vertical mill)"
REPLAY_START = pd.Timestamp("2026-10-01 06:00:00")
CYCLE = pd.Timedelta(minutes=5)

# Same columns and order as the Checkpoint 1 file (proposal screenshots); the last three are
# added for Task 1: source_file/source_row point to the AI4I line, tool_wear_before_min is the
# wear of the cycle just before a tool change.
EVENT_COLUMNS = [
    "event_id", "source_udi", "machine_id", "line_id", "timestamp", "event_type", "planned",
    "failure_modes", "downtime_min", "kpi_affected", "scrap_parts",
    "product_id", "product_type", "air_temp_k", "process_temp_k", "temp_delta_k",
    "rpm", "torque_nm", "power_w", "tool_wear_min",
    "source_file", "source_row", "tool_wear_before_min",
]


def load_raw(path: Path) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"[ERROR] {path} not found. Download ai4i2020.csv (see README, 'Source data').")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [c for c in AI4I_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"[ERROR] {path.name} lacks expected AI4I columns: {missing}")
    df = df[list(AI4I_COLUMNS)].rename(columns=AI4I_COLUMNS)
    df.insert(0, "source_row", df.index + 2)  # line number in the CSV file (header = line 1)
    for c in df.columns:
        if c != "source_row":
            df[c] = df[c].astype(str).str.strip()
    return df


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split rows into usable and rejected. Returns (clean, rejected)."""
    reasons = pd.Series("", index=df.index, dtype=object)

    def flag(mask: pd.Series, reason: str) -> None:
        sel = mask & (reasons == "")
        reasons[sel] = reason

    required = ["udi", "product_id", "product_type"] + NUMERIC[1:]
    flag(df[required].eq("").any(axis=1), "missing value")

    num = df[NUMERIC].apply(pd.to_numeric, errors="coerce")
    flag(num.isna().any(axis=1), "non-numeric value")
    flag(~num[FLAGS].isin([0, 1]).all(axis=1), "flag not 0/1")
    flag(~df["product_type"].isin(["L", "M", "H"]), "product type not L/M/H")

    udi = num["udi"]
    flag(udi.duplicated(keep="first") & udi.notna(), "duplicate UDI")
    flag(~udi.between(1, ROWS_PER_MACHINE * len(MACHINES)), "UDI outside 1-10000")

    clean = df[reasons == ""].copy()
    clean[NUMERIC] = num.loc[clean.index]
    for c in ["udi", "rpm", "tool_wear_min"] + FLAGS:
        clean[c] = clean[c].astype(int)

    # Rows with valid values but contradictory labels: kept for the tool-wear sequence,
    # but they produce no event and are reported as rejected.
    inconsistent = (clean[MODES].sum(axis=1) > 0) & (clean["machine_failure"] == 0)
    reasons.loc[clean.index[inconsistent]] = "mode flag without machine_failure"
    clean["inconsistent"] = inconsistent

    rejected = df[reasons != ""].copy()
    rejected = rejected.rename(columns={"udi": "source_udi"})
    rejected.insert(1, "reason", reasons[reasons != ""])
    rejected.insert(2, "flags", rejected[MODES].apply(
        lambda r: "|".join(m for m in MODES if str(r[m]) == "1"), axis=1))
    first = ["source_udi", "reason", "flags", "source_row"]
    return clean, rejected[first + [c for c in rejected.columns if c not in first]]


def construct_events(clean: pd.DataFrame, source_file: str) -> pd.DataFrame:
    d = clean.sort_values("udi").copy()
    block = (d["udi"] - 1) // ROWS_PER_MACHINE
    offset = (d["udi"] - 1) % ROWS_PER_MACHINE
    d["machine_id"] = block.map(lambda k: MACHINES[k][0])
    d["line_id"] = block.map(lambda k: MACHINES[k][1])
    d["timestamp"] = (REPLAY_START + offset * CYCLE).dt.strftime("%Y-%m-%d %H:%M:%S")
    d["temp_delta_k"] = (d["process_temp_k"] - d["air_temp_k"]).round(1)
    d["power_w"] = (d["torque_nm"] * d["rpm"] * 2 * math.pi / 60).round().astype(int)
    d["tool_wear_before_min"] = d.groupby("machine_id")["tool_wear_min"].shift(1)
    d["source_file"] = source_file

    # FAILURE events
    f = d[(d["machine_failure"] == 1)].copy()
    f["failure_modes"] = f[MODES].apply(
        lambda r: "|".join(m for m in MODES if r[m] == 1) or "UNSPECIFIED", axis=1)
    f["downtime_min"] = f["failure_modes"].map(
        lambda s: max(DOWNTIME_BY_MODE[m] for m in s.split("|")))
    f["event_id"] = f["udi"].map(lambda u: f"EVT-{u:05d}")
    f["event_type"] = "FAILURE"
    f["planned"] = False
    f["kpi_affected"] = "Availability|Quality"
    f["scrap_parts"] = 1
    f["tool_wear_before_min"] = pd.NA  # only meaningful for tool changes

    # TOOL_CHANGE events: wear drops compared with the previous cycle of the same machine
    t = d[d["tool_wear_min"] < d["tool_wear_before_min"]].copy()
    t["failure_modes"] = ""
    t["downtime_min"] = TOOL_CHANGE_DOWNTIME
    t["event_id"] = t["udi"].map(lambda u: f"TC-{u:05d}")
    t["event_type"] = "TOOL_CHANGE"
    t["planned"] = True
    t["kpi_affected"] = "Availability"
    t["scrap_parts"] = 0
    t["tool_wear_before_min"] = t["tool_wear_before_min"].astype(int)

    ev = pd.concat([f, t]).rename(columns={"udi": "source_udi"})
    # time order; a tool change listed before a failure in the same cycle (as in Checkpoint 1)
    ev = ev.sort_values(["timestamp", "machine_id", "event_type"], ascending=[True, True, False])
    return ev[EVENT_COLUMNS].reset_index(drop=True)


def machines_table(clean: pd.DataFrame) -> pd.DataFrame:
    block = (clean["udi"] - 1) // ROWS_PER_MACHINE
    m = clean.assign(machine_id=block.map(lambda k: MACHINES[k][0]), line_id=block.map(lambda k: MACHINES[k][1]))
    m = (m.groupby(["machine_id", "line_id"])
          .agg(udi_from=("udi", "min"), udi_to=("udi", "max"), cycles=("udi", "size")).reset_index())
    m["machine_model"] = MACHINE_MODEL
    return m


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    raw = load_raw(args.raw)
    clean, rejected = validate(raw)
    events = construct_events(clean, args.raw.name)

    args.out.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.out / "events.csv", index=False)
    rejected.to_csv(args.out / "rejected_records.csv", index=False)
    machines_table(clean).to_csv(args.out / "machines.csv", index=False)

    n_fail = int((events.event_type == "FAILURE").sum())
    n_tc = int((events.event_type == "TOOL_CHANGE").sum())
    print(f"[build_events] raw rows            : {len(raw):,}")
    print(f"[build_events] events              : {len(events):,} ({n_fail} FAILURE + {n_tc} TOOL_CHANGE)")
    print(f"[build_events] UNSPECIFIED failures: {int((events.failure_modes == 'UNSPECIFIED').sum())}")
    print(f"[build_events] rejected rows       : {len(rejected)}  "
          f"{rejected['reason'].value_counts().to_dict() if len(rejected) else ''}")
    print(f"[build_events] written to          : {args.out}")


if __name__ == "__main__":
    main()
