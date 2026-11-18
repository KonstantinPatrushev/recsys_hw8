"""Pilot without any LLM: classical channels and oracle bounds for the planned hybrid
-> evidence/pilot_headroom.json

The planned hybrid splits the Top-10 into a REPEAT channel (assets the user already bought,
newest first, exactly the latest_buy prefix) and an EXPLORE channel (never-bought eligible
assets). This pilot measures, under the course starter's protocol (imported, not modified):

  * explore-channel recall: share of never-bought future purchases found in the top-k
    never-bought list of popularity / starter CBF tokens / TF-IDF over the asset text
    (the same-information control planned for the LLM encoder);
  * encoder-only classical analogues: latest_buy with its popularity fill replaced by the
    CBF or TF-IDF explore list (allocation unchanged);
  * oracle bounds that use the truth (analysis only, never a model input):
      - best per-user split between the two channels (upper bound for any allocation ranker),
      - perfect order inside the repeat channel (upper bound for reranking past buys only).

Run: .venv/bin/python -I src/pilot_headroom.py
"""
from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import time
from collections import defaultdict
from datetime import date

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "FAR-Trans"
spec = importlib.util.spec_from_file_location("starter", ROOT / "baseline" / "far-trans" / "starter.py")
starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(starter)
CUTOFF = "2021-06-01"
K = 10


def asset_text(row):
    parts = [row.get("assetName", ""), row.get("assetShortName", "")]
    for key in ("assetCategory", "assetSubCategory", "sector", "industry", "marketID"):
        v = row.get(key, "").strip()
        if v and v not in ("Not_Available", "nan"):
            parts.append(f"{key} {v}")
    return " ".join(p for p in parts if p)


def fill(prefix, explore, k=K):
    out, seen = list(prefix[:k]), set(prefix[:k])
    for isin in explore:
        if len(out) >= k:
            break
        if isin not in seen:
            out.append(isin)
            seen.add(isin)
    return out


def main():
    t0 = time.perf_counter()
    assets, profiles, history, truth, end, excluded = starter.load_data(DATA, CUTOFF, 30)
    features = {isin: starter.tokens(row) for isin, row in assets.items()}
    pop = starter.popularity_scores(history, assets)
    pop_order = starter.order(pop)
    events = starter.scan_recent_events(DATA, CUTOFF, assets)
    # recent popularity: distinct buyers in the 90 days before the cutoff (past-only, classical)
    since = date.fromordinal(date.fromisoformat(CUTOFF).toordinal() - 90).isoformat()
    recent_buyers = defaultdict(set)
    for uid_, evs in events.items():
        for ts, isin, kind in evs:
            if kind == "Buy" and ts >= since:
                recent_buyers[isin].add(uid_)
    rpop_order = starter.order({i: len(recent_buyers.get(i, ())) * 1e6 + pop[i] for i in assets})
    demo = json.loads((ROOT / "outputs" / "baseline_demo100" / "protocol.json").read_text())["users"]
    warm = starter.select_users(profiles, history, "warm", 0, None)

    ids = sorted(assets)
    idx = {isin: i for i, isin in enumerate(ids)}
    vec = TfidfVectorizer(lowercase=True, token_pattern=r"(?u)\b\w+\b", sublinear_tf=True)
    T = vec.fit_transform([asset_text(assets[i]) for i in ids])  # rows are L2-normalised
    t_setup = time.perf_counter() - t0

    def run(users):
        sums = defaultdict(float)
        nonempty = 0
        rec = defaultdict(lambda: [0, 0])  # explore recall: [found, total]
        for uid in users:
            counts = history.get(uid, {})
            rel = truth.get(uid, set()) & set(assets)
            buy_last = {}
            for ts, isin, kind in events.get(uid, ()):
                if kind == "Buy" and isin in assets and (isin not in buy_last or ts > buy_last[isin]):
                    buy_last[isin] = ts
            repeat = sorted(buy_last, key=lambda i: (-date.fromisoformat(buy_last[i]).toordinal(), i))
            seen = set(counts) | set(repeat)
            e_pop = [i for i in pop_order if i not in seen]
            e_rpop = [i for i in rpop_order if i not in seen]
            freq = sorted(buy_last, key=lambda i: (-counts.get(i, 0), -date.fromisoformat(buy_last[i]).toordinal(), i))
            cbf = starter.content_scores(counts, features)
            e_cbf = [i for i in starter.order(cbf) if i not in seen]
            u = np.zeros(T.shape[1])
            for isin, n in counts.items():
                u += n * T[idx[isin]].toarray().ravel()
            sim = T @ u if u.any() else np.zeros(len(ids))
            e_txt = [ids[j] for j in sorted(range(len(ids)), key=lambda j: (-sim[j], ids[j])) if ids[j] not in seen]
            lists = {
                "latest_buy (repeat newest-first + popularity fill)": fill(repeat, e_pop),
                "repeat + CBF-token explore fill": fill(repeat, e_cbf),
                "repeat + TF-IDF-text explore fill": fill(repeat, e_txt),
                "repeat + recent-popularity (90 days) explore fill": fill(repeat, e_rpop),
                "repeat ordered by buy count, then recency + popularity fill": fill(freq, e_pop),
                "explore only: popularity, never-bought": e_pop[:K],
                "explore only: TF-IDF text, never-bought": e_txt[:K],
            }
            for name, lst in lists.items():
                sums[name] += starter.ndcg10(lst, rel)
            if rel:
                nonempty += 1
                # oracle 1: best split m repeat slots + (10 - m) explore slots, per explore source
                for name, ex in (("popularity", e_pop), ("recent popularity 90d", e_rpop), ("TF-IDF text", e_txt)):
                    best = max(starter.ndcg10(fill(repeat[:m], ex), rel) for m in range(0, min(K, len(repeat)) + 1))
                    sums[f"oracle split: repeat newest-first + {name} explore"] += best
                # oracle 2: perfect order inside the repeat channel, popularity fill unchanged
                rep_sorted = sorted(repeat, key=lambda i: (i not in rel, repeat.index(i)))
                sums["oracle order inside repeat channel + popularity fill"] += starter.ndcg10(fill(rep_sorted, e_pop), rel)
                new = rel - seen
                for name, ex in (("popularity", e_pop), ("recent popularity 90d", e_rpop), ("CBF tokens", e_cbf), ("TF-IDF text", e_txt)):
                    for k in (10, 50):
                        rec[f"{name}@{k}"][0] += len(new & set(ex[:k]))
                        rec[f"{name}@{k}"][1] += len(new)
        n = len(users)
        out = {"users": n, "nonempty_truth_users": nonempty, "methods": {}}
        for name, s in sums.items():
            if name.startswith("oracle"):
                out["methods"][name] = {"ndcg_at_10": round(s / n, 6), "ndcg_at_10_nonempty": round(s / nonempty, 6)}
            else:
                out["methods"][name] = {"ndcg_at_10": round(s / n, 6), "ndcg_at_10_nonempty": round(s / nonempty, 6) if nonempty else None}
        out["explore_recall_of_never_bought_purchases"] = {
            k: {"found": f, "total": t, "recall": round(f / t, 4) if t else None} for k, (f, t) in rec.items()}
        return out

    res = {"cutoff": CUTOFF, "end_exclusive": end, "k": K, "eligible_assets": len(assets),
           "tfidf_vocabulary": len(vec.vocabulary_), "setup_seconds": round(t_setup, 1)}
    for name, users in (("demo_100", demo), ("warm_all", warm)):
        t1 = time.perf_counter()
        res[name] = run(users)
        res[name]["seconds"] = round(time.perf_counter() - t1, 1)
        print(name, json.dumps(res[name], indent=1, ensure_ascii=False), flush=True)
    (ROOT / "evidence" / "pilot_headroom.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
