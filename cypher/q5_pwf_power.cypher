// Q5. How do power failures (PWF) split into low- and high-power cases, by line and variant?
// Path: ProductVariant <-OF_VARIANT- Product <-SCRAPPED- Event -HAS_FAILURE_MODE-> FailureMode;
//       Event -OCCURRED_ON-> Machine -PART_OF-> ProductionLine (5 hops)
// AI4I rule: PWF when power < 3500 W or > 9000 W. power_w is rounded to whole watts.
MATCH (:FailureMode {code: 'PWF'})<-[:HAS_FAILURE_MODE]-(e:Failure)-[:OCCURRED_ON]->(:Machine)-[:PART_OF]->(l:ProductionLine),
      (e)-[:SCRAPPED]->(:Product)-[:OF_VARIANT]->(v:ProductVariant)
WITH e, l, v,
     CASE WHEN e.power_w > 9000 THEN 'HIGH' WHEN e.power_w < 3500 THEN 'LOW' ELSE 'INSIDE_3500_9000' END AS power_class
RETURN power_class, l.line_id AS line_id, v.code AS variant, count(e) AS events
ORDER BY power_class, line_id, variant;
