# MySQL Read-only Setup

Database creation and controlled fact-data import are documented in
[`database_rebuild.md`](database_rebuild.md). Complete that process with a DBA
account before creating the runtime read-only account below.

1. Open MySQL Workbench with a DBA account.
2. Open `scripts/setup_readonly_user.sql`.
3. Replace `YOUR_PASSWORD_HERE` locally in Workbench with a strong password. Do not save that password into the project.
4. Confirm the target schema is `agentic_marketing`, then execute the script.
5. Put connection values into a local `.env` or the process environment. `.env` is ignored by source control.
6. Run `python scripts/run_agent_real.py "南京客户有多少？" --execute`.
7. Confirm `database_capability.readonly_verified=true`, `SELECT` is present, and `forbidden_privileges` is empty.

If you cannot create users or grants, ask the DBA to perform steps 1–4 and provide only the runtime account through the approved secret channel. Do not grant `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, or `ALL PRIVILEGES`.

The template uses `'agent_readonly_user'@'localhost'`. If TCP connection to `127.0.0.1` does not match this account under the server's host-resolution policy, ask the DBA to create the equivalent least-privilege account for `'agent_readonly_user'@'127.0.0.1'`; do not broaden it to `%` without an explicit network-security decision.

Verification SQL:

```sql
SHOW GRANTS FOR 'agent_readonly_user'@'localhost';
```

After signing in as the read-only user and selecting the schema:

```sql
SELECT CURRENT_USER();
SELECT DATABASE();
SHOW GRANTS FOR CURRENT_USER();
```

The grants should contain `SELECT` (and may contain `USAGE`) only. They must not contain `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, or `ALL PRIVILEGES`.

The web application is a localhost competition demo and does not implement user
authentication. Keep the default `127.0.0.1` bind. A remote bind requires the
explicit `--allow-remote` acknowledgement and is not an authorization control.
