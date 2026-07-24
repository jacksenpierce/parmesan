#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from parmesan.migration import migrate_v1_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate a PGX Pasta v1 database into Parmesan 2.0.")
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate_v1_database(args.source, args.destination, overwrite=args.overwrite), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
