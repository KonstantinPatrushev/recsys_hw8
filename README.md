# LLM4Rec project on FAR-Trans, Hybrid track: Session 1 (HW7) plan and Session 2 (HW8) implementation

Konstantin Patrushev, HSE LLM4Rec. Research question (planned): does a repeat-aware LLM hybrid — an open-weight
embedding encoder proposing never-bought assets plus an open-weight LLM ranker ordering the customer's past assets
together with those proposals — improve nDCG@10 over the latest-buy baseline for warm FAR-Trans customers?

## Session 2 (HW8): Make It Run

Implemented arms on the starter's default protocol (100 warm demo users, cutoff 2021-06-01, 30-day window, repeats
allowed, starter nDCG@10): A0 = latest buy, A1 = rule + LLM-encoder fill, A2 = LLM ranker over past assets + 10 popular
never-bought assets, A3 = LLM ranker over past assets + 10 encoder candidates (the hybrid).

| Path | What |
|---|---|
| `src/hw2_hybrid.py` | the experiment: protocol through the starter's own functions, encoder, ranker, evaluation, checks |
| `src/hw2_analysis.py` | independent nDCG recompute from the raw CSV, per-arm diagnostics, the hand-check customer |
| `src/build_report_hw2.py` | renders the Session 2 report from `evidence/` |
| `evidence/hw2_metrics.json` | metrics, failed cases, runtime, model revisions, prompt instruction, hardware |
| `evidence/hw2_analysis.json`, `evidence/hw2_rule_only_10404users.json` | diagnostics; A0/A1 on all 10,404 warm users |

Models (open weights, pinned): encoder `Qwen/Qwen3-Embedding-0.6B` @ `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`,
ranker `Qwen/Qwen3-1.7B` @ `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` (greedy, thinking off, max 256 new tokens, bfloat16).
Dependencies: Python 3.12, torch 2.11.0, transformers 4.57.6, sentence-transformers 5.7.0, numpy, polars.
Hardware: Apple M5 (24 GB), PyTorch MPS.

```bash
uv pip install --python .venv/bin/python torch==2.11.0 transformers==4.57.6 sentence-transformers==5.7.0
# after the two starter runs in the Session 1 section below (they produce the reference protocol.json / metrics.json the script asserts against)
.venv/bin/python -I src/hw2_hybrid.py --dtype bfloat16               # 100 demo users, all arms (~30 min on M5)
.venv/bin/python -I src/hw2_hybrid.py --max-users 0 --rule-only --out outputs/hw2_rule_warm   # A0/A1 on all warm users
.venv/bin/python -I src/hw2_analysis.py && .venv/bin/python -I src/build_report_hw2.py --pdf
```

## Session 1 (HW7)

This part holds the classical pilot (no LLM) and the evidence behind every number in the Session 1 report.

| Path | What |
|---|---|
| `baseline/far-trans`, `baseline/far-trans-llm` | course starter and LLM baselines, unmodified copies of dryjins/RecSys-LLMs `project/` |
| `src/data_profile.py` | repeat vs new purchases, history length, profile-field status at four cutoffs |
| `src/pilot_headroom.py` | classical channels and oracle bounds for the planned hybrid |
| `src/data_example.py` | the real record shown in the report and the leakage checks |
| `src/pilot_encoder.py` | encoder-side pilot with Qwen3-Embedding-0.6B (needs torch + sentence-transformers) |
| `src/build_report.py` | renders the report from `evidence/` |
| `evidence/` | JSON outputs of the scripts above, starter metrics, verified literature |

Reproduce (Python 3.12):

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python polars numpy scikit-learn
# data: download FAR-Trans.zip from https://researchdata.gla.ac.uk/1658/ and unzip into data/raw/
(cd baseline/far-trans && ../../.venv/bin/python -I starter.py run --data-dir ../../data/raw/FAR-Trans --output-dir ../../outputs/baseline_demo100)
(cd baseline/far-trans && ../../.venv/bin/python -I starter.py run --data-dir ../../data/raw/FAR-Trans --output-dir ../../outputs/baseline_warm_all --max-users 0)
.venv/bin/python -I src/data_profile.py && .venv/bin/python -I src/pilot_headroom.py && .venv/bin/python -I src/data_example.py
```

The FAR-Trans data (CC BY 4.0) is not redistributed here.
