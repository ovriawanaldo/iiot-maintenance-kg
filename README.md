# IIoT Maintenance Knowledge Graph

Linking CNC failure events to manufacturer troubleshooting knowledge.

Course project for **Knowledge Graphs and LLMs** (Prof. R. V. Davydov), Peter the Great St. Petersburg Polytechnic University, 2026.
Author: Putra Ovriawan Aldo Pribadi, group 5140901/51701.

The graph connects structured failure events (built from the AI4I 2020 dataset) with facts extracted from Haas Automation troubleshooting guides, so a maintenance engineer can see which components to inspect and which actions to take after a machine fails. The full plan is in [`docs/proposal/proposal_v6.pdf`](docs/proposal/proposal_v6.pdf).

## Status

| Stage | Deadline | Status |
|---|---|---|
| Proposal | 3 Nov 2026 | Accepted |
| Task 1: initial graph from structured data | 1 Dec 2026 (discussion 17 Nov) | In progress |
| Task 2: knowledge extracted from text | Credit day (discussion 15 Dec) | Not started |

## Repository structure

```
data/
  raw/            original sources (AI4I 2020, pilot Haas passages)
  constructed/    events.csv, machines.csv, rejected_records.csv (built by scripts/build_events.py)
scripts/          Python scripts that build the data and the graph
cypher/           constraints and the Cypher queries for Q1–Q11
results/          saved query results and graph check reports
notebooks/        Jupyter notebooks for exploration and the defence demo
docs/
  proposal/       accepted project proposal (PDF)
  schema/         schema diagram (draw.io source + PNG)
```

## Data sources

| Source | Use | Licence / access |
|---|---|---|
| AI4I 2020 Predictive Maintenance Dataset, Matzka (2020), UCI ML Repository, [doi:10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C) | Structured records (Task 1) | CC BY 4.0, unchanged copy in `data/raw/ai4i2020.csv` |
| Haas Automation troubleshooting guides (TG0009, TG0051, Standard Coolant NGC, …), haascnc.com | Unstructured text (Task 2) | Public web pages, © Haas Automation: only URLs, retrieval dates, passage IDs and short excerpts are stored |

AI4I 2020 is a published synthetic benchmark that reflects real industrial predictive-maintenance data. See [`data/README.md`](data/README.md) for column descriptions.

## Rebuild

Requirements: Python 3.11+, and Docker for Neo4j 5 (from Task 1 on).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 1. Build the constructed events dataset from AI4I (deterministic)
python scripts/build_events.py
# expected output: {'FAILURE': 339, 'TOOL_CHANGE': 119} rejected 18
```

Graph loading, checks and queries will be added here during Task 1.

## Use of AI tools

Claude (Anthropic) assisted with planning, drafting the proposal and writing scripts. I reviewed, ran and verified all code and results myself. If an LLM is used for extraction in Task 2 (planned: Llama 3.1 8B via Ollama, temperature 0), the model version, run dates, settings, prompts and raw outputs will be saved in this repository so the graph can be rebuilt without new model calls.
