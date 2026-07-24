#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from parmesan import catalog


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    (root / "TOOL_CATALOG.json").write_text(
        json.dumps(catalog("core"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    secondary = (
        catalog("advanced")
        + catalog("maintenance")
        + catalog("compatibility")
    )
    (root / "maintenance" / "TOOL_CATALOG.json").write_text(
        json.dumps(secondary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
