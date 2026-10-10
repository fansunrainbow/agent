# Real MySQL Read-only Execution Integration Report

## Integration status

The production path is implemented, but no live connection was attempted because `DB_HOST`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` were absent. Thus `real_db` remains `false` and execution-accuracy metrics remain `not_measured`.

## Safety architecture

Only deterministic artifacts reach execution: validated Query Plan → deterministic SQL Generator → AST/Schema/Security/Join/Cost/Parameter Guards → `EXPLAIN FORMAT=JSON` → real-cost gate → parameterized execution → Result Validator. There is no raw-SQL API or executable LLM-SQL path.

Configuration is environment-only. SQLAlchemy supplies pooling, pre-ping, connection timeout, and recycle; PyMySQL supplies the driver. The adapter sets `TRANSACTION READ ONLY` and `MAX_EXECUTION_TIME`, converts named placeholders into driver bindings without interpolating values, and preserves separate SQL/params.

The capability check runs `SELECT 1` and inspects `SHOW GRANTS FOR CURRENT_USER`. It fails closed if write/DDL privileges are present and never issues a destructive probe. `scripts/setup_readonly_user.sql` contains only a password placeholder.

## Operation

- Dry run: `python scripts/run_agent_real.py "南京客户有多少？" --dry-run`
- Real execution: `python scripts/run_agent_real.py "南京客户有多少？" --execute`
- Web: `python scripts/run_web.py`

The benchmark harness enforces 30–50 cases, independent `gold_source`, explicit Gold Results, and scalar/set/grouped/ranking comparison. It emits all five required artifacts and records stage latency. It rejects Agent-generated Gold.
