# MT_009 Silent-ignore Hotfix Report

## Result

`EXPLICIT_MUTATION_MUST_SUCCEED_OR_FAIL_CLOSED` is implemented. MT_009 now returns `needs_clarification`; it cannot retain Diamond and return `ready` after “普通客户” fails grounding.

Every Patch change records `patch_operation`, `patch_target`, `old_value`, `requested_new_value`, `resolution_status`, and `patch_status`. Aggregate status is `APPLIED`, `PARTIALLY_APPLIED`, `NEEDS_CLARIFICATION`, `UNSUPPORTED`, or `FAILED`.

An explicit replacement residue not explained by a registry-backed Grounded Condition creates a fail-closed Patch. The prior confirmed value may remain only as conversation context; the plan becomes non-executable. Detection uses mutation markers, grounded surfaces, and parent-plan semantics—never benchmark IDs or complete benchmark queries.

Eight dedicated tests cover unknown and ambiguous levels, valid Gold-level replacement, unknown city, unknown metric, valid removal, failed-mutation presentation, and New Task isolation.

Final full regression: `205/205` PASS.

The frozen MT_009 Gold still claims “普通客户” means Gold card (`1000003`). It was not modified for score chasing; the system correctly rejects that unregistered mapping.
