# Graph checks

| Check | Result | Detail |
|---|---|---|
| C1 identifier uniqueness | PASS | all keys present and unique |
| C2 required properties | PASS | no missing required property |
| C3 relationship types and endpoints | PASS | all relationships allowed |
| C4 cardinalities | PASS | all cardinality rules hold |
| C5 provenance on every node and relationship | PASS | 0 nodes and 0 relationships without source/derivation |
| C6 graph matches events.csv | PASS | all equal: {'Failure': 339, 'ToolChange': 119, 'HAS_FAILURE_MODE': 364, 'AFFECTS_KPI': 797, 'Product': 339, 'SourceRecord': 455, 'total downtime_min': 15940} |

Total nodes: 1270, relationships: 2763

## Nodes by label
- Event: 458
- Failure: 339
- FailureMode: 6
- KPI: 2
- Machine: 4
- MachineModel: 1
- Product: 339
- ProductVariant: 3
- ProductionLine: 2
- SourceRecord: 455
- ToolChange: 119

## Relationships by type
- AFFECTS_KPI: 797
- DERIVED_FROM: 458
- HAS_FAILURE_MODE: 364
- INSTANCE_OF: 4
- OCCURRED_ON: 458
- OF_VARIANT: 339
- PART_OF: 4
- SCRAPPED: 339

Manual verification sample (20 events): reports/manual_verification_sample.csv
