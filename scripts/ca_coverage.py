#!/usr/bin/env python
"""Measure corporate-action adjustment coverage against the staged CA archive.

Maintainer tool -- reads ``nse-data/`` only, never writes, not run in CI.

    uv run python scripts/ca_coverage.py [--root nse-data]
    uv run python scripts/ca_coverage.py --with-bse --from 2022-01-01 --to 2024-12-31

The table shows, per corporate-action type, how many staged records carry terms
this library can turn into a price divisor today. Re-run after each change to see
the number move. ``--with-bse`` additionally probes how many NSE records that
*don't* parse have a name+ex-date match in BSE's free corporate-actions feed.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from powernse.corporate_actions import SUBJECTS, CorporateActionType, ex_date_of, face_value_of, symbol_of

# Projection helper for rights terms -- replaced by SubjectClassifier.rights_terms
# once that lands. Percentage dividends + consolidation are already in the classifier.
_RIGHTS_RATIO = re.compile(r"rights\b[^0-9]*?(\d+)\s*:\s*(\d+)", re.IGNORECASE)
_RIGHTS_PREM = re.compile(r"(?:prem(?:ium)?|@)\D*?(?:rs|re)?\.?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_RIGHTS_PAR = re.compile(r"at\s*par", re.IGNORECASE)
_RIGHTS_NON_EQUITY = re.compile(r"warrant|ccps|pccps|\bncd\b|\bpcd\b|debenture|\bfcd\b|partly\s*paid", re.IGNORECASE)


def _dividend_parses(record: dict) -> bool:
    subject = SUBJECTS.subject_of(record)
    return SUBJECTS.dividend_amount(subject, face_value=face_value_of(record)) is not None


def _rights_parses(subject: str) -> bool:
    if _RIGHTS_NON_EQUITY.search(subject) or not _RIGHTS_RATIO.search(subject):
        return False
    return bool(_RIGHTS_PREM.search(subject) or _RIGHTS_PAR.search(subject))


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
            bucket, hit = "bonus/split/consolidation", SUBJECTS.price_factor(subject) is not None
        elif ca_type is CorporateActionType.CONSOLIDATION:
            bucket, hit = "bonus/split/consolidation", SUBJECTS.consolidation_factor(subject) is not None
        elif ca_type is CorporateActionType.DIVIDEND:
            bucket, hit = "dividend", _dividend_parses(record)
        elif ca_type is CorporateActionType.RIGHTS:
            bucket, hit = "rights", _rights_parses(subject)
        else:
            continue
        total[bucket] += 1
        parsed[bucket] += int(hit)

    print(f"{len(records)} records across {len(by_type)} classified types\n")
    print(f"{'type':<26}{'count':>8}")
    for name, count in by_type.most_common():
        print(f"{name:<26}{count:>8}")
    print(f"\n{'adjustable terms':<26}{'parsed':>10}{'total':>8}{'rate':>8}")
    for bucket in ("bonus/split/consolidation", "dividend", "rights"):
        got, tot = parsed[bucket], total[bucket]
        rate = f"{100 * got / tot:.1f}%" if tot else "n/a"
        print(f"{bucket:<26}{got:>10}{tot:>8}{rate:>8}")


def _unparsed_events(records: list[dict], lo: date, hi: date) -> list[tuple[str, date, str]]:
    out: list[tuple[str, date, str]] = []
    for record in records:
        ex = ex_date_of(record)
        if ex is None or not (lo <= ex <= hi):
            continue
        subject = SUBJECTS.subject_of(record)
        ca_type = SUBJECTS.classify(subject)
        if ca_type is CorporateActionType.DIVIDEND and not _dividend_parses(record):
            out.append((symbol_of(record).upper(), ex, subject))
        elif ca_type is CorporateActionType.RIGHTS and not _rights_parses(subject):
            out.append((symbol_of(record).upper(), ex, subject))
    return out


def _bse_index(lo: date, hi: date) -> dict[tuple[str, date], str]:
    import requests  # noqa: PLC0415 -- maintainer script, optional dependency path

    url = "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/", "Accept": "application/json"}
    index: dict[tuple[str, date], str] = {}
    span = hi.year - lo.year
    for offset in range(span + 1):
        year = lo.year + offset
        start = max(lo, date(year, 1, 1))
        end = min(hi, date(year, 12, 31))
        params = {
            "Fdate": start.strftime("%Y%m%d"),
            "TDate": end.strftime("%Y%m%d"),
            "ddlcategorys": "E",
            "ddlindex": "",
            "scripcode": "",
            "segment": "Equity",
            "strSearch": "",
        }
        rows = requests.get(url, params=params, headers=headers, timeout=45).json()
        for row in rows:
            name = str(row.get("short_name", "")).upper()
            try:
                ex = datetime.strptime(str(row.get("Ex_date", "")), "%d %b %Y").date()  # noqa: DTZ007
            except ValueError:
                continue
            index[name, ex] = str(row.get("Purpose", ""))
    return index


def _probe_bse(records: list[dict], lo: date, hi: date) -> None:
    unparsed = _unparsed_events(records, lo, hi)
    print(f"\nNSE unparsed dividend/rights events in {lo}..{hi}: {len(unparsed)}")
    bse = _bse_index(lo, hi)
    print(f"BSE corporate-action rows fetched: {len(bse)}")
    hits = sum(any((name, ex + timedelta(days=delta)) in bse for delta in (-1, 0, 1)) for name, ex, _ in unparsed)
    rate = f"{100 * hits / len(unparsed):.1f}%" if unparsed else "n/a"
    print(f"of those, BSE has a name+ex-date(+/-1d) match for: {hits} ({rate})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("nse-data"))
    parser.add_argument("--with-bse", action="store_true", help="probe BSE backfill for unparsed events")
    three_years_ago = date.today() - timedelta(days=1095)  # noqa: DTZ011 -- naive date is intended
    parser.add_argument("--from", dest="from_date", type=date.fromisoformat, default=three_years_ago)
    parser.add_argument("--to", dest="to_date", type=date.fromisoformat, default=date.today())  # noqa: DTZ011
    args = parser.parse_args()

    records = _load_records(args.root)
    _coverage_table(records)
    if args.with_bse:
        _probe_bse(records, args.from_date, args.to_date)


if __name__ == "__main__":
    main()
