#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from parmesan.manifest import build_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Parmesan manifests from SQLite.")
    parser.add_argument("database")
    parser.add_argument("--json", dest="output_json")
    parser.add_argument("--markdown", dest="output_markdown")
    args = parser.parse_args()
    manifest = build_manifest(args.database, args.output_json, args.output_markdown)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
