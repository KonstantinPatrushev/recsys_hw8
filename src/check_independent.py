"""Independent re-implementation (polars, no starter code) of the headline data facts
-> evidence/check_independent.json

Recomputes, at cutoff 2021-06-01 with a 30-day window: eligible assets, warm customers, customers with a
future purchase, future purchase pairs and how many of them repeat an earlier Buy; and latest-buy nDCG@10 on
the warm cohort (repeat list newest first with ISIN tie-break, popularity fill). Compares with the files
produced through the starter (data_profile.json, baseline_warm_all_metrics.json).

Run: .venv/bin/python -I src/check_independent.py
"""
from __future__ import annotations

import json
import math
import pathlib
from datetime import date, timedelta

import polars as pl

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = ROOT / "data" / "raw" / "FAR-Trans"
CUT = "2021-06-01"
END = (date.fromisoformat(CUT) + timedelta(days=30)).isoformat()


def main():
    s = lambda f: pl.read_csv(D / f, infer_schema_length=0)
    assets = s("asset_information.csv").filter(pl.col("timestamp").str.slice(0, 10) < CUT)["ISIN"].unique()
    priced = (s("close_prices.csv").filter((pl.col("timestamp").str.slice(0, 10) < CUT) &
                                          (pl.col("closePrice").cast(pl.Float64) > 0))["ISIN"].unique())
    eligible = set(assets.to_list()) & set(priced.to_list())
    prof = s("customer_information.csv").filter(pl.col("timestamp").str.slice(0, 10) < CUT)["customerID"].unique()
    tx = (s("transactions.csv").unique(maintain_order=True)                      # exact duplicate rows
          .filter(pl.col("transactionID").cast(pl.Int64) >= 0)                  # reconstructed positions
          .with_columns(pl.col("timestamp").str.slice(0, 10).alias("day")))
    buys = tx.filter((pl.col("transactionType") == "Buy") & pl.col("ISIN").is_in(list(eligible)))
    hist = buys.filter(pl.col("day") < CUT)
    fut = buys.filter((pl.col("day") >= CUT) & (pl.col("day") < END))
    warm = set(hist["customerID"].unique().to_list()) & set(prof.to_list())
    hist_pairs = set(map(tuple, hist.select(["customerID", "ISIN"]).unique().iter_rows()))
    fut_pairs = {p for p in map(tuple, fut.select(["customerID", "ISIN"]).unique().iter_rows()) if p[0] in warm}
    repeat = sum(1 for p in fut_pairs if p in hist_pairs)
    nonempty = {u for u, _ in fut_pairs}

    # latest-buy nDCG@10 on the warm cohort
    pop = hist.group_by("ISIN").agg(pl.col("customerID").n_unique().alias("n"))
    popd = dict(pop.iter_rows())
    pop_order = sorted(eligible, key=lambda i: (-popd.get(i, 0), i))
    last = hist.group_by(["customerID", "ISIN"]).agg(pl.col("day").max().alias("last"))
    by_user = {}
    for u, i, d in last.iter_rows():
        by_user.setdefault(u, []).append((d, i))
    truth = {}
    for u, i in fut_pairs:
        truth.setdefault(u, set()).add(i)
    total = 0.0
    for u in warm:
        rep = [i for d, i in sorted(by_user.get(u, []), key=lambda x: (-date.fromisoformat(x[0]).toordinal(), x[1]))][:10]
        lst = rep + [i for i in pop_order if i not in set(rep)][: 10 - len(rep)]
        t = truth.get(u, set())
        if t:
            gain = sum(1 / math.log2(k + 2) for k, i in enumerate(lst) if i in t)
            total += gain / sum(1 / math.log2(k + 2) for k in range(min(10, len(t))))
    mine = {"eligible_assets": len(eligible), "warm_users": len(warm), "nonempty_truth_users": len(nonempty),
            "truth_items": len(fut_pairs), "repeat_items": repeat, "share_repeat_items": round(repeat / len(fut_pairs), 4),
            "latest_buy_ndcg_all": total / len(warm), "latest_buy_ndcg_nonempty": total / len(nonempty)}
    prof_ = json.loads((ROOT / "evidence" / "data_profile.json").read_text())["cutoffs"][CUT]
    met = json.loads((ROOT / "evidence" / "baseline_warm_all_metrics.json").read_text())["methods"]["latest_buy"]
    ref = {"eligible_assets": prof_["eligible_assets"], "warm_users": prof_["warm_users"],
           "nonempty_truth_users": prof_["warm_cohort"]["nonempty_truth_users"], "truth_items": prof_["warm_cohort"]["truth_items"],
           "repeat_items": prof_["warm_cohort"]["repeat_items"], "share_repeat_items": prof_["warm_cohort"]["share_repeat_items"],
           "latest_buy_ndcg_all": met["ndcg_at_10"], "latest_buy_ndcg_nonempty": met["ndcg_at_10_nonempty"]}
    match = {k: (abs(mine[k] - ref[k]) < 1e-12 if isinstance(mine[k], float) else mine[k] == ref[k]) for k in mine}
    out = {"independent": mine, "starter_based": ref, "match": match, "all_match": all(match.values())}
    (ROOT / "evidence" / "check_independent.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
