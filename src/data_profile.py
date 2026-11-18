"""Data profile that motivates the research question -> evidence/data_profile.json

Uses the course starter's own loading rules (imported, not modified): as-of metadata, eligible
assets, Buy history strictly before the cutoff, truth = future Buy in the 30-day window
intersected with the eligible set, reconstructed initial positions and exact duplicates excluded.

For the warm cohort (users with at least one pre-cutoff Buy) it reports
  * how many future purchases repeat an asset the user already bought vs. a never-bought asset,
  * how far the never-bought purchases are from the user's history (shared category / market),
  * where they sit in the global popularity order,
  * history length and profile-field status (observed / estimated / missing),
for the default cutoff and three more cutoffs as a stability check.

Run: .venv/bin/python -I src/data_profile.py
"""
from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import statistics
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "FAR-Trans"
spec = importlib.util.spec_from_file_location("starter", ROOT / "baseline" / "far-trans" / "starter.py")
starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(starter)

CUTOFFS = ["2020-06-01", "2021-01-01", "2021-06-01", "2022-01-01"]
DEFAULT = "2021-06-01"


def quantiles(values, qs=(0.25, 0.5, 0.75, 0.9)):
    if not values:
        return {}
    s = sorted(values)
    return {str(q): s[min(len(s) - 1, int(math.floor(q * len(s))))] for q in qs}


def profile_cutoff(cutoff, demo_users=None):
    assets, profiles, history, truth, end, excluded = starter.load_data(DATA, cutoff, 30)
    warm = [u for u in profiles if history.get(u)]
    pop = starter.popularity_scores(history, assets)
    pop_order = starter.order(pop)
    pop_rank = {isin: r for r, isin in enumerate(pop_order, 1)}
    out = {"cutoff": cutoff, "end_exclusive": end, "eligible_assets": len(assets),
           "warm_users": len(warm), "excluded_rows": excluded}

    def composition(users):
        n_users = n_items = n_repeat = n_new = 0
        users_any_new = users_only_new = users_only_repeat = 0
        new_same_cat = new_same_sub = new_same_market = new_in_pop10 = 0
        new_pop_ranks = []
        cat_counts = Counter()
        for u in users:
            t = truth.get(u, set()) & set(assets)
            if not t:
                continue
            n_users += 1
            hist = set(history.get(u, {}))
            rep = t & hist
            new = t - hist
            n_items += len(t)
            n_repeat += len(rep)
            n_new += len(new)
            users_any_new += bool(new)
            users_only_new += bool(new) and not rep
            users_only_repeat += bool(rep) and not new
            cats = {assets[i]["assetCategory"] for i in hist}
            subs = {(assets[i]["assetCategory"], assets[i]["assetSubCategory"]) for i in hist}
            mkts = {assets[i]["marketID"] for i in hist}
            pop_new_order = [i for i in pop_order if i not in hist][:10]
            for i in t:
                cat_counts[assets[i]["assetCategory"]] += 1
            for i in new:
                new_same_cat += assets[i]["assetCategory"] in cats
                new_same_sub += (assets[i]["assetCategory"], assets[i]["assetSubCategory"]) in subs
                new_same_market += assets[i]["marketID"] in mkts
                new_in_pop10 += i in pop_new_order
                new_pop_ranks.append(pop_rank[i])
        r = lambda a, b: round(a / b, 4) if b else None
        return {
            "nonempty_truth_users": n_users, "truth_items": n_items,
            "repeat_items": n_repeat, "new_items": n_new, "share_repeat_items": r(n_repeat, n_items),
            "users_with_any_new_item": users_any_new, "users_with_only_new_items": users_only_new,
            "users_with_only_repeat_items": users_only_repeat,
            "new_items_sharing_category_with_history": r(new_same_cat, n_new),
            "new_items_sharing_category_and_subcategory_with_history": r(new_same_sub, n_new),
            "new_items_sharing_market_with_history": r(new_same_market, n_new),
            "new_items_in_top10_popularity_excluding_history": r(new_in_pop10, n_new),
            "new_items_global_popularity_rank_quantiles": quantiles(new_pop_ranks),
            "truth_items_by_category": dict(cat_counts.most_common()),
        }

    out["warm_cohort"] = composition(warm)
    if demo_users is not None:
        out["demo_100"] = composition(demo_users)
    if cutoff == DEFAULT:
        hl = [len(history[u]) for u in warm]
        out["history_distinct_assets_quantiles_warm"] = quantiles(hl)
        out["share_warm_users_with_1_asset"] = round(sum(1 for x in hl if x == 1) / len(hl), 4)
        out["share_warm_users_with_le3_assets"] = round(sum(1 for x in hl if x <= 3) / len(hl), 4)
        status = {k: Counter() for k in ("customerType", "riskLevel", "investmentCapacity")}
        for u in warm:
            ctx = starter.profile_context(profiles[u])
            for k in status:
                status[k][ctx[k]["status"]] += 1
        out["profile_status_warm"] = {k: dict(v) for k, v in status.items()}
        cats = Counter(a["assetCategory"] for a in assets.values())
        out["eligible_assets_by_category"] = dict(cats.most_common())
        named = sum(1 for a in assets.values() if a.get("sector", "").strip() not in ("", "Not_Available"))
        out["eligible_assets_with_sector"] = named
    return out


def main():
    demo = json.loads((ROOT / "outputs" / "baseline_demo100" / "protocol.json").read_text())["users"]
    res = {"source": "course starter rules (baseline/far-trans/starter.py), FAR-Trans archive 10.5525/gla.researchdata.1658",
           "cutoffs": {}}
    for c in CUTOFFS:
        res["cutoffs"][c] = profile_cutoff(c, demo if c == DEFAULT else None)
        w = res["cutoffs"][c]["warm_cohort"]
        print(c, {k: w[k] for k in ("nonempty_truth_users", "truth_items", "share_repeat_items",
                                     "users_with_any_new_item", "users_with_only_new_items")}, flush=True)
    (ROOT / "evidence" / "data_profile.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    d = res["cutoffs"][DEFAULT]
    print(json.dumps({k: v for k, v in d.items() if k != "excluded_rows"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
