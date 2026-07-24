from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timezone

RFC3339_NS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{9}Z$")


def now_rfc3339_ns() -> str:
    ns = time.time_ns()
    sec, nano = divmod(ns, 1_000_000_000)
    dt = datetime.fromtimestamp(sec, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{nano:09d}Z"


def unique_timestamp(connection: sqlite3.Connection, table: str, column: str = "created_at") -> str:
    if not table.replace("_", "").isalnum() or not column.replace("_", "").isalnum():
        raise ValueError("unsafe SQL identifier")
    query = f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1"
    while True:
        value = now_rfc3339_ns()
        if connection.execute(query, (value,)).fetchone() is None:
            return value
        time.sleep(0)


def is_rfc3339_ns(value: str) -> bool:
    return bool(RFC3339_NS_RE.fullmatch(value))
