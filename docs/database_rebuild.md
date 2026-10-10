# Real DB Rebuild Guide

## Data boundary

The submission package includes the four dimension/entity CSV files needed for
deterministic semantic resolution. The following customer fact files are
controlled competition data and are intentionally not redistributed:

- `dws_cust_aset_d_202606021051.csv`
- `dws_cust_fin_d_202606021050.csv`
- `dwd_cust_tran_d_202606021051.csv`
- `dwd_cust_hold_d_202606021051.csv`

Obtain them only through the approved competition data channel. Put them in the
project root alongside the included CSV files, then verify size and SHA-256:

```powershell
python scripts/verify_external_data.py
```

The expected values are frozen in `EXTERNAL_DATA_REQUIREMENTS.json`. Do not use
a similarly named or regenerated dataset when reproducing the Frozen Benchmark.

## Create and load MySQL

Run all commands from the project root. The import SQL uses relative filenames,
so it no longer contains a developer-machine path. Use a DBA login path rather
than placing a password on the command line:

```powershell
mysql_config_editor set --login-path=agentic_dba --host=127.0.0.1 --user=root --password
mysql --login-path=agentic_dba --execute="source sql/01_create_database.sql"
mysql --login-path=agentic_dba agentic_marketing --execute="source 表描述_MySQL8.sql"

$importScripts = @(
  "sql/05_import_dim_public.sql",
  "sql/07_import_dim_branch.sql",
  "sql/09_import_dim_product.sql",
  "sql/11_import_ads_cust_info_d.sql",
  "sql/13_import_dws_cust_aset_d.sql",
  "sql/15_import_dws_cust_fin_d.sql",
  "sql/17_import_dwd_cust_tran_d.sql",
  "sql/19_import_dwd_cust_hold_d.sql"
)
foreach ($script in $importScripts) {
  mysql --login-path=agentic_dba --local-infile=1 agentic_marketing --execute="source $script"
  if ($LASTEXITCODE -ne 0) { throw "Import failed: $script" }
}

mysql --login-path=agentic_dba agentic_marketing --execute="source sql/21_check_all_counts.sql"
mysql --login-path=agentic_dba agentic_marketing --execute="source sql/22_check_customer_joins.sql"
mysql --login-path=agentic_dba agentic_marketing --execute="source sql/23_check_product_joins.sql"
```

If the MySQL client resolves relative `LOCAL INFILE` paths differently in your
environment, pass `--data-dir` to the verifier for the approved directory and
copy the verified files to the project root before import. Do not edit the SQL
back to an absolute user-profile path.

## Runtime account and verification

After import, follow `docs/mysql_readonly_setup.md` to create the SELECT-only
runtime account. Then run:

```powershell
python scripts/check_real_db.py
python scripts/run_agent_real.py "南京客户有多少？" --execute
```

The four currently disclosed `COST_BLOCK` cases remain safety-limited on the
frozen schema. Do not raise the one-million-row guard threshold merely to change
the score; resolve them through reviewed indexing/query-plan optimization and a
new explicitly authorized benchmark freeze.
