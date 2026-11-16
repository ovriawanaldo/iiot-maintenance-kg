#!/usr/bin/env bash
# Rebuild the Task 1 graph from scratch and produce every report.
# Needs: data/raw/ai4i2020.csv, a running Neo4j 5, NEO4J_PASSWORD exported.
set -euo pipefail
cd "$(dirname "$0")"
python scripts/build_events.py
python scripts/load_graph.py --reset
python scripts/load_graph.py            # second import: counts must stay the same
python scripts/check_graph.py
python scripts/answers_pandas.py
python scripts/run_queries.py
python scripts/export_graph.py
