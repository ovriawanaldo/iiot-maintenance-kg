# Data

## raw/

**`ai4i2020.csv`**: AI4I 2020 Predictive Maintenance Dataset (Matzka, 2020), UCI Machine Learning Repository, [doi:10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C), licence CC BY 4.0. Unchanged; 10,000 rows × 14 columns, 339 rows with `Machine failure = 1`.

| Column | Meaning |
|---|---|
| UDI | Unique row identifier (1–10,000) |
| Product ID | Product serial, prefixed by its variant |
| Type | Product variant: L (low), M (medium), H (high quality) |
| Air temperature [K], Process temperature [K] | Temperatures in kelvin |
| Rotational speed [rpm], Torque [Nm] | Spindle speed and torque |
| Tool wear [min] | Minutes the current tool has been used |
| Machine failure | 1 if the process failed |
| TWF, HDF, PWF, OSF, RNF | Failure-mode flags: tool wear, heat dissipation, power, overstrain, random |

**`haas_passages.csv`**: pilot sample of five abridged passages from Haas Automation troubleshooting guides (guide ID, URL, last-updated date, symptom, possible cause, corrective action). The full passage set is collected in Task 2.

## constructed/

Built from `raw/ai4i2020.csv` by `scripts/build_events.py`. The script uses no random numbers, so it always produces the same files.

**`events.csv`**: 458 events (339 FAILURE, 119 TOOL_CHANGE), 23 columns. The first 20 are the Checkpoint 1 columns (same values and row order); the last 3 were added in Task 1.

| Column | Origin | Rule |
|---|---|---|
| event_id | constructed | `EVT-` (failure) or `TC-` (tool change) + 5-digit UDI |
| source_udi | AI4I | UDI of the source row |
| machine_id, line_id | constructed | UDI 1–2500 → CNC-01, 2501–5000 → CNC-02, 5001–7500 → CNC-03, 7501–10000 → CNC-04; CNC-01/02 → LINE-A, CNC-03/04 → LINE-B |
| timestamp | constructed | 2026-10-01 06:00 + 5 min × position within the machine block |
| event_type, planned | constructed | FAILURE if Machine failure = 1; TOOL_CHANGE (planned) if tool wear resets |
| failure_modes | computed | Flags joined with `|`; UNSPECIFIED if no flag is set |
| downtime_min | constructed | Scenario parameter: TWF 25, HDF 45, PWF 60, OSF 35, RNF/UNSPECIFIED 15 (maximum if several modes); tool change 10 |
| kpi_affected, scrap_parts | constructed | Failure → Availability and Quality, 1 scrapped part; tool change → Availability |
| product_id, product_type, air_temp_k, process_temp_k, rpm, torque_nm, tool_wear_min | AI4I | Copied unchanged |
| temp_delta_k, power_w | computed | process − air temperature; torque × rpm × 2π / 60 |
| source_file, source_row | AI4I | File name and line number of the source row (header = line 1) |
| tool_wear_before_min | AI4I | Tool changes only: tool wear of the previous cycle of the same machine, i.e. the wear at which the tool was changed |

**`machines.csv`**: the four machines, their UDI range, cycle count and (assumed) machine model.

**`rejected_records.csv`**: AI4I rows that do not fit the schema, kept here instead of being dropped silently: `source_udi`, `reason`, `flags`, `source_row`, then the original values. In AI4I these are 18 rows with a failure-mode flag (all RNF) but `Machine failure = 0`. The script also rejects missing or non-numeric values, flags other than 0/1, unknown product types, duplicate UDIs and UDIs outside 1–10,000; none occur in AI4I.
