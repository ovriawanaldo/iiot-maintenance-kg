// Q2. On which machines do heat-dissipation failures (HDF) occur, and under which process conditions?
// Path: FailureMode <-HAS_FAILURE_MODE- Event -OCCURRED_ON-> Machine -PART_OF-> ProductionLine
// Check: AI4I rule says HDF needs temp difference < 8.6 K and speed < 1380 rpm.
MATCH (:FailureMode {code: 'HDF'})<-[:HAS_FAILURE_MODE]-(e:Failure)-[:OCCURRED_ON]->(m:Machine)-[:PART_OF]->(l:ProductionLine)
RETURN m.machine_id AS machine_id, l.line_id AS line_id, count(e) AS hdf_events,
       sum(e.downtime_min) AS downtime_min,
       max(e.temp_delta_k) AS max_temp_delta_k, max(e.rpm) AS max_rpm
ORDER BY hdf_events DESC, machine_id;
