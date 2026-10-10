from __future__ import annotations

from getpass import getpass
import json
from pathlib import Path
import sys

from dotenv import dotenv_values
import pymysql


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "benchmark" / "reports" / "real_db_final" / "user_setup_status.json"
ACCOUNT_USER = "agent_readonly_user"
ACCOUNT_HOST = "localhost"
FORBIDDEN = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "ALL PRIVILEGES")


def save_status(status: str, error: str | None = None) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": status, "account": f"{ACCOUNT_USER}@{ACCOUNT_HOST}", "error": error}
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    values = dotenv_values(ROOT / ".env")
    new_password = values.get("DB_PASSWORD")
    if not new_password:
        print("本机 .env 的密码项为空，已停止。")
        save_status("FAILED", "local .env password is empty")
        return 2

    dba_user = input("请输入已有 MySQL DBA 用户名（必须明确输入，不会自动使用 root）：").strip()
    if not dba_user:
        print("未输入 DBA 用户名，已停止。")
        save_status("FAILED", "DBA username was not provided")
        return 2
    dba_password = getpass("请输入 DBA 密码（输入不会显示，也不会保存）：")
    if not dba_password:
        print("未输入 DBA 密码，已停止。")
        save_status("FAILED", "DBA password was not provided")
        return 2

    connection = None
    try:
        connection = pymysql.connect(
            host=str(values.get("DB_HOST") or "127.0.0.1"),
            port=int(values.get("DB_PORT") or 3306),
            user=dba_user,
            password=dba_password,
            connect_timeout=5,
            autocommit=False,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE USER IF NOT EXISTS 'agent_readonly_user'@'localhost' IDENTIFIED BY %s",
                (new_password,),
            )
            cursor.execute(
                "ALTER USER 'agent_readonly_user'@'localhost' IDENTIFIED BY %s",
                (new_password,),
            )
            cursor.execute("REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'agent_readonly_user'@'localhost'")
            cursor.execute("GRANT SELECT ON `agentic_marketing`.* TO 'agent_readonly_user'@'localhost'")
            cursor.execute("SHOW GRANTS FOR 'agent_readonly_user'@'localhost'")
            grants = [str(row[0]) for row in cursor.fetchall()]
        connection.commit()
        upper = "\n".join(grants).upper()
        forbidden = sorted(item for item in FORBIDDEN if item in upper)
        if "SELECT" not in upper or forbidden:
            raise PermissionError(f"只读授权验证失败；检测到禁止权限: {forbidden}")
        print("只读账号已创建/更新，授权验证 PASS。")
        print("账号: agent_readonly_user@localhost")
        print("权限: SELECT only")
        save_status("PASS")
        return 0
    except Exception as exc:
        if connection is not None:
            connection.rollback()
        message = f"{type(exc).__name__}: {exc}"
        print("创建失败：" + message)
        save_status("FAILED", message)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
