"""Encoder-side pilot for the planned hybrid -> evidence/pilot_encoder.json

Embeds the text of every eligible asset (name, short name and the starter's metadata fields)
with an open-weight embedding LLM and uses it exactly like the TF-IDF control in
src/pilot_headroom.py: user vector = buy-count-weighted sum of the user's past assets,
cosine similarity, never-bought assets only.  Same information, different representation.

Reported: explore recall of never-bought future purchases @10/@50, nDCG@10 of
"repeat newest-first + LLM-embedding explore fill", the oracle split with the LLM explore
list, and the encoding time.  Analysis only: the ranker part of the hybrid is not run here.

Run: .venv/bin/python -I src/pilot_encoder.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import platform
import time
from datetime import date

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "FAR-Trans"
spec = importlib.util.spec_from_file_location("starter", ROOT / "baseline" / "far-trans" / "starter.py")
starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(starter)
spec2 = importlib.util.spec_from_file_location("pilot", ROOT / "src" / "pilot_headroom.py")
pilot = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(pilot)

MODEL = "Qwen/Qwen3-Embedding-0.6B"
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
CUTOFF, K = "2021-06-01", 10


def main():
    assets, profiles, history, truth, end, _ = starter.load_data(DATA, CUTOFF, 30)
    pop = starter.popularity_scores(history, assets)
    pop_order = starter.order(pop)
    events = starter.scan_recent_events(DATA, CUTOFF, assets)
    warm = starter.select_users(profiles, history, "warm", 0, None)
    demo = json.loads((ROOT / "outputs" / "baseline_demo100" / "protocol.json").read_text())["users"]
    ids = sorted(assets)
    texts = [pilot.asset_text(assets[i]) for i in ids]

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    t0 = time.perf_counter()
    model = SentenceTransformer(MODEL, revision=REVISION, device=device)
    t_load = time.perf_counter() - t0
    t1 = time.perf_counter()
    E = model.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
    t_enc = time.perf_counter() - t1
    idx = {isin: i for i, isin in enumerate(ids)}

    def run(users):
        s_fill = s_oracle = 0.0
        nonempty = 0
        rec = {10: [0, 0], 50: [0, 0]}
        for uid in users:
            counts = history.get(uid, {})
            rel = truth.get(uid, set()) & set(assets)
            buy_last = {}
            for ts, isin, kind in events.get(uid, ()):
                if kind == "Buy" and (isin not in buy_last or ts > buy_last[isin]):
                    buy_last[isin] = ts
            repeat = sorted(buy_last, key=lambda i: (-date.fromisoformat(buy_last[i]).toordinal(), i))
            seen = set(counts) | set(repeat)
            u = np.zeros(E.shape[1])
            for isin, n in counts.items():
                u += n * E[idx[isin]]
            sim = E @ u
            e_llm = [ids[j] for j in sorted(range(len(ids)), key=lambda j: (-sim[j], ids[j])) if ids[j] not in seen]
            s_fill += starter.ndcg10(pilot.fill(repeat, e_llm), rel)
            if rel:
                nonempty += 1
                s_oracle += max(starter.ndcg10(pilot.fill(repeat[:m], e_llm), rel)
                                for m in range(0, min(K, len(repeat)) + 1))
                new = rel - seen
                for k in rec:
                    rec[k][0] += len(new & set(e_llm[:k]))
                    rec[k][1] += len(new)
        n = len(users)
        return {"users": n, "nonempty_truth_users": nonempty,
                "repeat + LLM-embedding explore fill": {"ndcg_at_10": round(s_fill / n, 6),
                                                        "ndcg_at_10_nonempty": round(s_fill / nonempty, 6)},
                "oracle split: repeat newest-first + LLM-embedding explore": {"ndcg_at_10": round(s_oracle / n, 6),
                                                                             "ndcg_at_10_nonempty": round(s_oracle / nonempty, 6)},
                "explore_recall_of_never_bought_purchases": {
                    f"LLM embedding@{k}": {"found": f, "total": t, "recall": round(f / t, 4) if t else None}
                    for k, (f, t) in rec.items()}}

    res = {"model": MODEL, "revision": REVISION, "device": device, "torch": torch.__version__,
           "platform": platform.platform(), "assets_embedded": len(ids), "embedding_dim": int(E.shape[1]),
           "load_seconds": round(t_load, 1), "encode_seconds": round(t_enc, 1),
           "text_fields": "assetName, assetShortName, assetCategory, assetSubCategory, sector, industry, marketID",
           "demo_100": run(demo), "warm_all": run(warm)}
    (ROOT / "evidence" / "pilot_encoder.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
