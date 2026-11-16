// Q6. Per machine, how many planned tool changes and tool-wear failures (TWF), and at what tool wear?
// Path: Machine <-OCCURRED_ON- Event:ToolChange ; Machine <-OCCURRED_ON- Event:Failure -HAS_FAILURE_MODE-> FailureMode
// tool_wear_before_min = wear of the cycle just before the reset.
MATCH (m:Machine)
OPTIONAL MATCH (m)<-[:OCCURRED_ON]-(tc:ToolChange)
WITH m, count(tc) AS tool_changes,
     min(tc.tool_wear_before_min) AS change_wear_min, max(tc.tool_wear_before_min) AS change_wear_max
OPTIONAL MATCH (m)<-[:OCCURRED_ON]-(f:Failure)-[:HAS_FAILURE_MODE]->(:FailureMode {code: 'TWF'})
RETURN m.machine_id AS machine_id, tool_changes, change_wear_min, change_wear_max,
       count(f) AS twf_failures, min(f.tool_wear_min) AS twf_wear_min, max(f.tool_wear_min) AS twf_wear_max
ORDER BY machine_id;
