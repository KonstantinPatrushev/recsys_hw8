# LLM4Rec project, Session 1 (HW7): FAR-Trans study plan, Hybrid track

Konstantin Patrushev, HSE LLM4Rec. Research question (planned): does a repeat-aware LLM hybrid — an open-weight
embedding encoder proposing never-bought assets plus an open-weight LLM ranker ordering the customer's past assets
together with those proposals — improve nDCG@10 over the latest-buy baseline for warm FAR-Trans customers?

This repository holds the classical pilot (no LLM) and the evidence behind every number in the Session 1 report.

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
