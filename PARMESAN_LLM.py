#!/usr/bin/env python3
"""Self-locating conversational entry point for the Parmesan source artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))


def _dependency_failure(exc: ModuleNotFoundError) -> int:
    payload = {
        "ready": False,
        "error": "missing_runtime_dependency",
        "missing_module": exc.name,
        "next_action": "Install the dependencies listed in requirements.txt, then rerun this command.",
        "command": f"{sys.executable} -m pip install -r {ROOT / 'requirements.txt'}",
    }
    print(json.dumps(payload, indent=2))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Direct LLM entry for Parmesan. Start with: python PARMESAN_LLM.py doctor"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_parser = sub.add_parser("doctor", help="Check runtime and optional corpus readiness.")
    doctor_parser.add_argument("database", nargs="?")

    catalog_parser = sub.add_parser("catalog", help="Print a machine-readable tool catalog.")
    catalog_parser.add_argument(
        "--profile",
        choices=("core", "advanced", "maintenance", "compatibility", "all"),
        default="core",
    )

    dispatch_parser = sub.add_parser("dispatch", help="Run one JSON tool request.")
    group = dispatch_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", dest="request_json")
    group.add_argument("--file", dest="request_file")

    args = parser.parse_args()
    try:
        from parmesan import catalog, dispatch, doctor
    except ModuleNotFoundError as exc:
        return _dependency_failure(exc)

    if args.command == "doctor":
        output = doctor(args.database)
    elif args.command == "catalog":
        output = catalog(args.profile)
    else:
        raw = args.request_json if args.request_json is not None else Path(args.request_file).read_text(encoding="utf-8")
        output = dispatch(json.loads(raw))

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if not isinstance(output, dict) or output.get("ready", output.get("ok", True)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
