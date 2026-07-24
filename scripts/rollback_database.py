#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore an exact SQLite backup over a target path.")
    parser.add_argument("backup")
    parser.add_argument("target")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    backup = Path(args.backup)
    target = Path(args.target)
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    if args.expected_sha256 and digest != args.expected_sha256:
        raise SystemExit(f"backup checksum mismatch: {digest}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, target)
    print(f"restored {target} from {backup}; sha256={digest}")


if __name__ == "__main__":
    main()
