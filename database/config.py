from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    connect_timeout: int = 5
    query_timeout: int = 30
    pool_size: int = 5
    pool_recycle: int = 1800

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "DatabaseConfig":
        load_dotenv(env_path or PROJECT_ROOT / ".env", override=False)
        required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise RuntimeError("缺少数据库环境变量: " + ", ".join(missing))
        return cls(
            host=os.environ["DB_HOST"], port=int(os.getenv("DB_PORT", "3306")),
            name=os.environ["DB_NAME"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
            connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
            query_timeout=int(os.getenv("DB_QUERY_TIMEOUT", "30")),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
        )

    @property
    def url(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.user)}:{quote_plus(self.password)}@"
            f"{self.host}:{self.port}/{self.name}?charset=utf8mb4"
        )

    def safe_summary(self) -> dict[str, object]:
        return {"host": self.host, "port": self.port, "database": self.name, "user": self.user, "password": "***"}
