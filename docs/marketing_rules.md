# Marketing Rule Registry

All Stage 7 decisions are loaded from `marketing/rules/*.yaml`. Adding an effective, registry-valid rule does not require a Python change.

Every rule has `rule_id`, `name`, `version`, `effective_from`, optional `effective_to`, and a source from `internal_config`, `business_policy`, or `user_defined`.

## Tags — 9

- `high_asset`
- `high_cash_ratio`
- `stock_preference`
- `fund_low_allocation`
- `trade_active`
- `net_inflow`
- `net_outflow`
- `asset_growth`
- `asset_decline`

## Segments — 5

- `high_asset_low_fund`
- `high_level_outflow_decline`
- `fund_low_allocation`
- `positive_flow_or_growth` — verifies OR semantics.
- `active_non_outflow` — verifies nested NOT semantics.

## Opportunities — 6

- `fund_allocation_opportunity`
- `cash_allocation_opportunity`
- `active_concentrated_trading`
- `high_level_outflow_attention`
- `asset_decline_outflow_attention`
- `large_recent_inflow_followup`

These are transparent rule decisions, not response, purchase, or churn predictions.

## Strategies — 6

- fund allocation communication;
- asset allocation communication;
- product category structure communication;
- high-level customer maintenance;
- asset and fund-flow attention;
- recent inflow follow-up.

No strategy names a concrete financial product or claims that a product is suitable.

## Condition format

A leaf condition refers to a registered feature and an operator:

```yaml
feature: fund_holding_ratio
operator: lt
parameter: fund_ratio_threshold
```

Boolean nodes use `logic: AND|OR|NOT` and `conditions`. Unknown features and unsupported operators fail registry loading. A rule cannot silently introduce a new customer property.
