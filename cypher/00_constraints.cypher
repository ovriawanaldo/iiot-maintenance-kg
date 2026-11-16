// Uniqueness constraints on the stable identifiers (run by scripts/load_graph.py).
// Every load MERGEs on these keys, so repeated imports cannot create duplicates.
CREATE CONSTRAINT event_event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.event_id IS UNIQUE;
CREATE CONSTRAINT machine_machine_id IF NOT EXISTS FOR (n:Machine) REQUIRE n.machine_id IS UNIQUE;
CREATE CONSTRAINT productionline_line_id IF NOT EXISTS FOR (n:ProductionLine) REQUIRE n.line_id IS UNIQUE;
CREATE CONSTRAINT machinemodel_model_id IF NOT EXISTS FOR (n:MachineModel) REQUIRE n.model_id IS UNIQUE;
CREATE CONSTRAINT failuremode_code IF NOT EXISTS FOR (n:FailureMode) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT kpi_kpi_id IF NOT EXISTS FOR (n:KPI) REQUIRE n.kpi_id IS UNIQUE;
CREATE CONSTRAINT product_product_id IF NOT EXISTS FOR (n:Product) REQUIRE n.product_id IS UNIQUE;
CREATE CONSTRAINT productvariant_code IF NOT EXISTS FOR (n:ProductVariant) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT sourcerecord_udi IF NOT EXISTS FOR (n:SourceRecord) REQUIRE n.udi IS UNIQUE;
