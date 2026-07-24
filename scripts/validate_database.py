#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from parmesan.store import SQLitePGXStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate all Parmesan database invariants.")
    parser.add_argument("database")
    parser.add_argument("--shallow", action="store_true")
    args = parser.parse_args()
    report = SQLitePGXStore(args.database).validate_database(full=not args.shallow)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
