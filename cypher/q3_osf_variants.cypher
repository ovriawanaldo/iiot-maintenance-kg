// Q3. Which product variant is scrapped most by overstrain failures (OSF) on each line?
// Path: ProductVariant <-OF_VARIANT- Product <-SCRAPPED- Event -HAS_FAILURE_MODE-> FailureMode;
//       Event -OCCURRED_ON-> Machine -PART_OF-> ProductionLine (5 hops)
MATCH (:FailureMode {code: 'OSF'})<-[:HAS_FAILURE_MODE]-(e:Failure)-[:SCRAPPED]->(p:Product)-[:OF_VARIANT]->(v:ProductVariant),
      (e)-[:OCCURRED_ON]->(:Machine)-[:PART_OF]->(l:ProductionLine)
RETURN v.code AS variant, l.line_id AS line_id, count(DISTINCT p) AS scrapped_products
ORDER BY variant, line_id;
