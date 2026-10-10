# Stage 7 Tests and Manual Acceptance

## Automated verification

Run:

```powershell
python -m pytest tests/marketing -q
```

Coverage includes Feature Builder, Tag, Segment, Customer 360, Cohort, Opportunity, Strategy, Explainability, configuration-only generalization, time consistency, hallucination refusal and specific-product suitability refusal.

The generalization test copies the rule registry, adds one bond-allocation Tag, Segment and Opportunity only in YAML, and verifies that unchanged engines load and execute them.

The hallucination tests request risk preference, purchase intent, churn probability, income level, marital status and customer satisfaction. Each returns `UNSUPPORTED_CUSTOMER_ATTRIBUTE` and no invented value.

## Manual acceptance CLI

Production exports should come directly from Stage 6 `ExecutionManager`. The bundled JSON is explicitly synthetic and requires opt-in:

```powershell
python scripts/run_marketing_demo.py `
  --input tests/marketing/fixtures/stage6_safe_result.json `
  --allow-demo-fixture
```

Risk-preference refusal:

```powershell
python scripts/run_marketing_demo.py `
  --input tests/marketing/fixtures/stage6_safe_result.json `
  --allow-demo-fixture `
  --attribute risk_preference
```

Specific-fund recommendation refusal:

```powershell
python scripts/run_marketing_demo.py `
  --input tests/marketing/fixtures/stage6_safe_result.json `
  --allow-demo-fixture `
  --specific-product "某具体基金"
```

Try another configured segment with `--segment high_level_outflow_decline`. To change a threshold without code, pass parameters through the engine API or change the rule’s YAML defaults and rerun.

## Expected acceptance outcomes

1. High-asset/low-fund customer is selected with two metric evidence records.
2. High-level/outflow/decline customer is selected only when all three facts are present in one time range.
3. Customer 360 exposes six profile sections and evidence-backed tags.
4. Fund-low-allocation cohort analysis reports registered dimensions and metrics only.
5. Opportunities include actual values, thresholds, source, version and time range.
6. Explanations expose operator-level pass/fail evidence.
7. A bond-low-allocation rule can be added in YAML only.
8. User/business threshold overrides immediately change decisions and preserve threshold source.
9. Unsupported risk preference is refused.
10. Concrete product recommendation is refused without suitability data.
