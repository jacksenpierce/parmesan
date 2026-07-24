#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid

from parmesan.store import SQLitePGXStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild reference occurrences and FTS from current revisions.")
    parser.add_argument("database")
    parser.add_argument("--request-id", default=None)
    args = parser.parse_args()
    request_id = args.request_id or str(uuid.uuid4())
    print(json.dumps(SQLitePGXStore(args.database).rebuild_derived(request_id=request_id), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
