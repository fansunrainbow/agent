USE agentic_marketing;

WITH asset_ranked AS (
    SELECT
        pty_id,
        data_dt,
        COALESCE(nm_tot_aset, 0)
        + COALESCE(fc_pur_aset, 0) AS total_asset,

        ROW_NUMBER() OVER (
            PARTITION BY pty_id
            ORDER BY data_dt ASC
        ) AS rn_start,

        ROW_NUMBER() OVER (
            PARTITION BY pty_id
            ORDER BY data_dt DESC
        ) AS rn_end

    FROM dws_cust_aset_d
    WHERE data_dt BETWEEN '20260101' AND '20260331'
),

asset_period AS (
    SELECT
        pty_id,

        MAX(
            CASE
                WHEN rn_start = 1
                THEN total_asset
            END
        ) AS period_start_asset,

        MAX(
            CASE
                WHEN rn_end = 1
                THEN total_asset
            END
        ) AS period_end_asset

    FROM asset_ranked
    GROUP BY pty_id
),

fund_flow AS (
    SELECT
        pty_id,

        SUM(
            COALESCE(cash_in, 0)
            + COALESCE(tran_in, 0)
            + COALESCE(assign_in, 0)
        ) AS total_inflow,

        SUM(
            COALESCE(cash_out, 0)
            + COALESCE(tran_out, 0)
            + COALESCE(assign_out, 0)
        ) AS total_outflow

    FROM dws_cust_fin_d
    WHERE data_dt BETWEEN '20260101' AND '20260331'
    GROUP BY pty_id
)

SELECT
    a.pty_id,
    a.period_start_asset,
    a.period_end_asset,

    COALESCE(f.total_inflow, 0) AS total_inflow,
    COALESCE(f.total_outflow, 0) AS total_outflow,

    a.period_end_asset
    - a.period_start_asset
    + COALESCE(f.total_outflow, 0)
    - COALESCE(f.total_inflow, 0) AS asset_profit

FROM asset_period a

LEFT JOIN fund_flow f
    ON a.pty_id = f.pty_id

ORDER BY asset_profit DESC

LIMIT 20;