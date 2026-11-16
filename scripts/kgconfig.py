"""Shared settings: paths, Neo4j connection, and the allowed schema used by the checks."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_CSV = ROOT / "data" / "constructed" / "events.csv"
RAW_CSV = ROOT / "data" / "raw" / "ai4i2020.csv"
REPORTS = ROOT / "reports"
RESULTS = ROOT / "results"
QUERIES = ROOT / "cypher"
MACHINES_CSV = ROOT / "data" / "constructed" / "machines.csv"
EXPORT = ROOT / "graph_export"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# label -> stable identifier property
NODE_KEYS = {
    "Event": "event_id",
    "Machine": "machine_id",
    "ProductionLine": "line_id",
    "MachineModel": "model_id",
    "FailureMode": "code",
    "KPI": "kpi_id",
    "Product": "product_id",
    "ProductVariant": "code",
    "SourceRecord": "udi",
}

# label -> properties that must be present (besides the key)
REQUIRED_PROPS = {
    "Event": ["event_type", "timestamp", "planned", "downtime_min", "rpm", "torque_nm",
              "tool_wear_min", "source", "derivation"],
    "Machine": ["source", "derivation"],
    "ProductionLine": ["source", "derivation"],
    "MachineModel": ["name", "source", "derivation"],
    "FailureMode": ["name", "source", "derivation"],
    "KPI": ["name", "source", "derivation"],
    "Product": ["source", "derivation"],
    "ProductVariant": ["name", "source", "derivation"],
    "SourceRecord": ["file", "row", "source", "derivation"],
}

# Allowed (start label, relationship type, end label). Event also carries :Failure or :ToolChange.
ALLOWED_RELS = {
    ("Event", "OCCURRED_ON", "Machine"),
    ("Event", "HAS_FAILURE_MODE", "FailureMode"),
    ("Event", "AFFECTS_KPI", "KPI"),
    ("Event", "SCRAPPED", "Product"),
    ("Event", "DERIVED_FROM", "SourceRecord"),
    ("Product", "OF_VARIANT", "ProductVariant"),
    ("Machine", "PART_OF", "ProductionLine"),
    ("Machine", "INSTANCE_OF", "MachineModel"),
}
ALLOWED_LABELS = set(NODE_KEYS) | {"Failure", "ToolChange"}


def get_driver():
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("[ERROR] Python package 'neo4j' missing: pip install -r requirements.txt") from exc
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    return driver


def run(session, cypher: str, **params):
    return [r.data() for r in session.run(cypher, **params)]
