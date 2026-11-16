// Q4. Which failure modes occur together in one event, and on which machines?
// Path: FailureMode <-HAS_FAILURE_MODE- Event -HAS_FAILURE_MODE-> FailureMode; Event -OCCURRED_ON-> Machine
// Counted per exact combination: TWF+PWF+OSF in one event is its own row, not part of OSF+PWF.
MATCH (e:Failure)-[:HAS_FAILURE_MODE]->(fm:FailureMode)
WITH e, fm ORDER BY fm.code
WITH e, collect(fm.code) AS modes
WHERE size(modes) >= 2
MATCH (e)-[:OCCURRED_ON]->(m:Machine)
RETURN reduce(s = head(modes), x IN tail(modes) | s + '+' + x) AS mode_combination,
       count(e) AS events, collect(DISTINCT m.machine_id) AS machines
ORDER BY events DESC, mode_combination;
