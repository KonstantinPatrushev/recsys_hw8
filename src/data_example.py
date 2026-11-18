"""One real record for the report and the leakage checks -> evidence/data_example.json

The record is a raw row of transactions.csv for a user of the course's 100-user demo cohort,
together with the as-of (strictly before the cutoff) profile and asset rows it joins to.
Leakage checks count fields or rows that would reveal information from after the cutoff.

Run: .venv/bin/python -I src/data_example.py
"""
from __future__ import annotations

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "FAR-Trans"
CUTOFF = "2021-06-01"
USER = "7F4C738BC9D4A144C518"          # first user of the starter's demo cohort
TRANSACTION_ID = "8992311"


def rows(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def anon(uid):
    return uid[:6] + "…"


def main():
    demo = json.loads((ROOT / "outputs" / "baseline_demo100" / "protocol.json").read_text())["users"]
    assert USER in demo
    tx = [r for r in rows("transactions.csv") if r["customerID"] == USER]
    record = next(r for r in tx if r["transactionID"] == TRANSACTION_ID)
    shown = dict(record, customerID=anon(record["customerID"]))
    prof = [r for r in rows("customer_information.csv") if r["customerID"] == USER]
    asof_prof = max((r for r in prof if r["timestamp"][:10] < CUTOFF), key=lambda r: r["timestamp"])
    asset = [r for r in rows("asset_information.csv") if r["ISIN"] == record["ISIN"]]
    asof_asset = max((r for r in asset if r["timestamp"][:10] < CUTOFF), key=lambda r: r["timestamp"])

    # leakage checks
    cust = list(rows("customer_information.csv"))
    q_after_row = sum(1 for r in cust if r["lastQuestionnaireDate"][:10] > r["timestamp"][:10])
    latest = {}
    for r in cust:
        if r["timestamp"][:10] < CUTOFF and (r["customerID"] not in latest or r["timestamp"] > latest[r["customerID"]]["timestamp"]):
            latest[r["customerID"]] = r
    q_after_cutoff = sum(1 for r in latest.values() if r["lastQuestionnaireDate"][:10] >= CUTOFF)
    cust_rows_after = sum(1 for r in cust if r["timestamp"][:10] >= CUTOFF)
    assets = list(rows("asset_information.csv"))
    asset_rows_after = sum(1 for r in assets if r["timestamp"][:10] >= CUTOFF)
    limit = list(rows("limit_prices.csv"))
    limit_after = sum(1 for r in limit if r["maxDate"][:10] >= CUTOFF)
    tx_after = sum(1 for r in rows("transactions.csv") if r["timestamp"][:10] >= CUTOFF)

    out = {
        "source": "FAR-Trans public release, University of Glasgow Enlighten 10.5525/gla.researchdata.1658, FAR-Trans.zip",
        "file": "transactions.csv",
        "record_shown": shown,
        "user_transactions_before_cutoff": [dict(r, customerID=anon(r["customerID"])) for r in tx if r["timestamp"][:10] < CUTOFF],
        "user_transactions_on_or_after_cutoff_count": sum(1 for r in tx if r["timestamp"][:10] >= CUTOFF),
        "asof_profile_row": dict(asof_prof, customerID=anon(asof_prof["customerID"])),
        "asof_asset_row": asof_asset,
        "cutoff": CUTOFF,
        "leakage_checks": {
            "customer_rows_with_lastQuestionnaireDate_after_row_timestamp": {"count": q_after_row, "of": len(cust)},
            "asof_profiles_at_cutoff_with_lastQuestionnaireDate_on_or_after_cutoff": {"count": q_after_cutoff, "of": len(latest)},
            "customer_information_rows_on_or_after_cutoff": {"count": cust_rows_after, "of": len(cust)},
            "asset_information_rows_on_or_after_cutoff": {"count": asset_rows_after, "of": len(assets)},
            "limit_prices_rows_whose_series_ends_on_or_after_cutoff (profitability spans the future)": {"count": limit_after, "of": len(limit)},
            "transactions_on_or_after_cutoff": tx_after,
        },
    }
    (ROOT / "evidence" / "data_example.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
