// Q1. Which production line lost the most unplanned downtime, and which failure mode
//     contributed most there?
// Path: ProductionLine <-PART_OF- Machine <-OCCURRED_ON- Event -HAS_FAILURE_MODE-> FailureMode (3 hops)
// Mode downtime = downtime of the events that carry the mode (a multi-mode event counts for each mode).
MATCH (l:ProductionLine)<-[:PART_OF]-(:Machine)<-[:OCCURRED_ON]-(e:Failure)
WITH l, count(e) AS failures, sum(e.downtime_min) AS downtime_min
MATCH (l)<-[:PART_OF]-(:Machine)<-[:OCCURRED_ON]-(e2:Failure)-[:HAS_FAILURE_MODE]->(fm:FailureMode)
WITH l, failures, downtime_min, fm, sum(e2.downtime_min) AS mode_downtime
ORDER BY mode_downtime DESC, fm.code
WITH l, failures, downtime_min, collect({code: fm.code, dt: mode_downtime})[0] AS top
RETURN l.line_id AS line_id, failures, downtime_min,
       top.code AS top_mode, top.dt AS top_mode_downtime_min
ORDER BY downtime_min DESC;
