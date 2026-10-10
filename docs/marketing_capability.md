# Stage 7 Marketing Capability

Stage 7 consumes only successful Stage 6 execution results. It does not query raw tables, recalculate Stage 2 metrics, or ask an LLM to classify customers.

```text
Stage 6 ExecutionResult(status=success)
  -> CustomerFeatureBuilder
  -> TagEngine
  -> SegmentEngine / CohortAnalysisService
  -> OpportunityDetector
  -> StrategyEngine
  -> ExplanationLayer
  -> Marketing Result + Trace
```

## Customer Feature contract

Each feature stores:

- registered `metric_id` or `dimension_id`;
- value;
- metric time range or attribute snapshot date;
- `stage6_safe_result` source;
- confidence;
- missing state: `observed`, `zero`, `no_record`, or `unknown`.

`None` metric results become `no_record`; they never become zero. A numeric zero remains an explicit `zero`. Dimensions with no value are `unknown`.

The initial profile supports every registered Stage 2 metric or dimension returned by Stage 6. Customer 360 organizes the requested first-version fields into basic, asset, holding, trading, fund-flow and allocation sections.

## Decision semantics

The common rule evaluator implements three-valued Boolean logic:

- `True`: rule matched;
- `False`: rule did not match;
- `None`: insufficient data or conflicting metric time ranges.

`AND`, `OR`, and `NOT` preserve unknown state. This prevents `NOT unknown` from being treated as a positive fact. Explicit absence rules must use `not_exists` and therefore depend on a `no_record` provenance state.

Threshold precedence is:

```text
user_input > business_config > rule default
```

The selected threshold source is included in every decision.

## Customer 360 and cohort analysis

Customer 360 returns basic attributes, assets, holdings, trading, fund flow, allocations, explainable tags, snapshot date, metric time range and trace.

Cohort analysis returns distinct customer count, asset scale, average assets and age, gender/level/city/branch distributions, allocation averages, trading activity and net flow. Missing and unknown values are excluded and disclosed rather than coerced to zero.

## Strategy safety

Strategies are category-level engagement suggestions only. Facts, rule decisions and suggestions use separate arrays and separate `type` fields. The policy currently states that suitability data is unavailable, so a request for a specific fund, stock or wealth product is rejected with `SUITABILITY_DATA_REQUIRED`.

Unsupported properties such as risk preference, purchase intent, churn probability, income, marital status or satisfaction are rejected unless they are later added to the registered data model with a legitimate source.

## Tool facade

`marketing/tools.py` exposes:

- `build_customer_profile()`
- `calculate_tags()`
- `evaluate_segment()`
- `analyze_segment()`
- `find_opportunities()`
- `get_strategy()`
- `explain_marketing_decision()`

The Agent should call these tools and must not reproduce their rule logic in prompts.
