#!/usr/bin/env python3
"""Marca como mora las cuotas vencidas sin cobrar (mismo job diario del API; útil como cron externo).

  python scripts/mark_overdue_payments.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.infrastructure.utils.default_scheduler import run_once  # noqa: E402


async def main(dry_run: bool) -> int:
    result = await run_once(dry_run=dry_run)
    if result is None:
        print("Otra instancia tiene el lock; nada que hacer.")
        return 0
    print(f"{'(simulación) ' if dry_run else ''}{result[0]} cuotas pasaron a mora en {result[1]} créditos")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().dry_run)))
