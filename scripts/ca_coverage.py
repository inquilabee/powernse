#!/usr/bin/env python
"""Measure corporate-action adjustment coverage against the staged CA archive.

Maintainer tool -- reads the archive only, never writes, not run in CI.

    uv run python scripts/ca_coverage.py [--root nse-data]
    uv run python scripts/ca_coverage.py --root nse-data --with-bse

The table shows, per corporate-action type, how many staged records carry terms
this library can turn into a price divisor. ``--with-bse`` additionally reports
how much a **staged** BSE corporate-actions archive lifts the dividend rate
(download it first: ``powernse bse-corporate-actions --from ... --to ...``).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

from powernse.archive import ArchiveRoot
from powernse.corporate_actions import SUBJECTS, CorporateActionType, ex_date_of, face_value_of, symbol_of
from powernse.reading import BseCorporateActionReader

RATIO_BUCKET = "bonus/split/consolidation"


def _dividend_parses(record: dict) -> bool:
    subject = SUBJECTS.subject_of(record)
    return SUBJECTS.dividend_amount(subject, face_value=face_value_of(record)) is not None


def _rights_parses(record: dict) -> bool:
    return SUBJECTS.rights_terms(SUBJECTS.subject_of(record), face_value=face_value_of(record)) is not None


def _load_records(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.glob("raw/corporate_actions/**/*.json")):
        records.extend(json.loads(path.read_text(encoding="utf-8")))
    return records


def _coverage_table(records: list[dict]) -> None:
    by_type: Counter[str] = Counter()
    parsed: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for record in records:
        subject = SUBJECTS.subject_of(record)
        ca_type = SUBJECTS.classify(subject)
        by_type[ca_type.value] += 1
        if ca_type in (CorporateActionType.BONUS, CorporateActionType.SPLIT):
            bucket, hit = RATIO_BUCKET, SUBJECTS.price_factor(subject) is not None
        elif ca_type is CorporateActionType.CONSOLIDATION:
            bucket, hit = RATIO_BUCKET, SUBJECTS.consolidation_factor(subject) is not None
        elif ca_type is CorporateActionType.DIVIDEND:
            bucket, hit = "dividend", _dividend_parses(record)
        elif ca_type is CorporateActionType.RIGHTS:
            bucket, hit = "rights", _rights_parses(record)
        else:
            continue
        total[bucket] += 1
        parsed[bucket] += int(hit)

    print(f"{len(records)} records across {len(by_type)} classified types\n")
    print(f"{'type':<26}{'count':>8}")
    for name, count in by_type.most_common():
        print(f"{name:<26}{count:>8}")
    print(f"\n{'adjustable terms':<26}{'parsed':>10}{'total':>8}{'rate':>8}")
    for bucket in (RATIO_BUCKET, "dividend", "rights"):
        got, tot = parsed[bucket], total[bucket]
        rate = f"{100 * got / tot:.1f}%" if tot else "n/a"
        print(f"{bucket:<26}{got:>10}{tot:>8}{rate:>8}")


def _bse_delta(records: list[dict], root: Path) -> None:
    ex_dates = [day for record in records if (day := ex_date_of(record)) is not None]
    if not ex_dates:
        return
    reader = BseCorporateActionReader(ArchiveRoot.connect(root))
    amounts = reader.dividend_amounts(min(ex_dates), max(ex_dates))
    print(f"\nstaged BSE dividend rows in span: {len(amounts)}")

    total = nse = bse = 0
    for record in records:
        if SUBJECTS.classify(SUBJECTS.subject_of(record)) is not CorporateActionType.DIVIDEND:
            continue
        total += 1
        if _dividend_parses(record):
            nse += 1
            continue
        ex, needle = ex_date_of(record), symbol_of(record).upper()
        if ex is not None and any((needle, ex + timedelta(days=d)) in amounts for d in (-1, 0, 1)):
            bse += 1
    if total:
        print(
            f"dividend parse rate: NSE {100 * nse / total:.1f}%  ->  "
            f"NSE+BSE {100 * (nse + bse) / total:.1f}%  (+{bse} records)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("nse-data"))
    parser.add_argument("--with-bse", action="store_true", help="also report the staged-BSE dividend backfill delta")
    args = parser.parse_args()

    records = _load_records(args.root)
    _coverage_table(records)
    if args.with_bse:
        _bse_delta(records, args.root)


if __name__ == "__main__":
    main()
