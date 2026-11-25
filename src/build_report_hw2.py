"""Render the Session 2 (HW2) report from evidence/ -> report/report_session2.html and the PDF.

Run: .venv/bin/python -I src/build_report_hw2.py [--pdf] [--commit <sha>]
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import subprocess
from decimal import ROUND_HALF_UP, Decimal

ROOT = pathlib.Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
REP = ROOT / "report"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PDF_NAME = "patrushev_konstantin_session2_report.pdf"
REPO = "https://github.com/KonstantinPatrushev/recsys_hw8"


def j(name):
    return json.loads((EV / name).read_text())


def rnd(x, d):
    return str(Decimal(str(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


f3 = lambda x: rnd(x, 3)
f4 = lambda x: rnd(x, 4)
pct = lambda x, d=0: rnd(100 * x, d) + "%"
n0 = lambda x: f"{int(x):,}"
esc = lambda s: html.escape(str(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--commit", default="[commit]")
    args = ap.parse_args()
    h = j("hw2_metrics.json")
    an = j("hw2_analysis.json")
    warm = j("hw2_rule_only_10404users.json")
    lit = j("literature.json")
    team = j("team_hw2.json")
    R = {x["key"]: x["n"] for x in lit["references"]}
    M, rt, fc = h["metrics"], h["runtime"], h["failed_cases"]
    cfg = h["config"]
    rk = cfg["ranker"]

    rows = [("Popularity", "popularity", f"{rt['protocol_and_baselines_s']} s*", "0"),
            ("CBF", "cbf", "(same run)*", "0"),
            ("Latest buy (= A0)", "latest_buy", "(same run)*", "0"),
            ("Latest buy or sell", "latest_buy_or_sell", "(same run)*", "0"),
            ("A1 encoder only: rule + LLM-encoder fill", "A1_rule_encoder_fill", f"{rt['encoder_embedding_s']} s", "0"),
            ("A2 ranker only: LLM ranker, popular candidates", "A2_llm_ranker_popularity",
             f"{rnd(rt['llm_generation_s']['A2'], 0)} s", str(fc.get('A2', 0))),
            ("<b>A3 hybrid: LLM ranker, encoder candidates</b>", "A3_llm_ranker_encoder_hybrid",
             f"{rnd(rt['llm_generation_s']['A3'] + rt['encoder_embedding_s'], 0)} s", str(fc.get('A3', 0)))]
    table = "".join(
        f"<tr><td>{lab}</td><td class=n>{M[k]['users']}</td><td class=n>{M[k]['nonempty_truth_users']}</td>"
        f"<td class=n>{f4(M[k]['ndcg_at_10'])}</td><td class=n>{f4(M[k]['ndcg_at_10_nonempty'])}</td>"
        f"<td class=n>{t}</td><td class=n>{f}</td></tr>" for lab, k, t, f in rows)
    W = warm["metrics"]
    lb, a1, a2, a3 = (M[k] for k in ("latest_buy", "A1_rule_encoder_fill", "A2_llm_ranker_popularity", "A3_llm_ranker_encoder_hybrid"))
    tok = rt["llm_tokens_in_out"]
    per_call = {a: rt["llm_generation_s"][a] / h["users"] for a in ("A2", "A3")}
    refs = "".join(f"<p>[{x['n']}] {x['ieee']}</p>" for x in lit["references"] if x["key"] in USED)
    num = {k: i + 1 for i, k in enumerate(USED)}
    refs = "".join(f"<p>[{num[x['key']]}] {x['ieee']}</p>" for x in sorted(
        (x for x in lit["references"] if x["key"] in USED), key=lambda x: num[x["key"]]))
    c = lambda k: f"[{num[k]}]"
    ex = an["example_user"]

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Session 2 Report &mdash; LLM ranker over past and new assets on FAR-Trans</title>
<style>
 a {{ color:#000; text-decoration:none; }} @page {{ size:A4; margin:12mm 13mm; }}
 body {{ font-family:"Times New Roman","Liberation Serif",serif; font-size:9.8pt; line-height:1.23; margin:0; }}
 h1 {{ font-size:14pt; text-align:center; margin:0 0 4pt; line-height:1.2; }}
 .meta {{ text-align:center; font-size:9.3pt; margin-bottom:5pt; }}
 h2 {{ font-size:10.4pt; margin:5pt 0 2pt; text-transform:uppercase; letter-spacing:.3pt; break-after:avoid; }}
 h3 {{ font-size:9.9pt; margin:3.5pt 0 1.5pt; font-style:italic; font-weight:normal; break-after:avoid; }}
 p {{ margin:0 0 2.8pt; text-align:justify; }} ul {{ margin:0 0 2.8pt; padding-left:14pt; }} li {{ margin-bottom:.8pt; text-align:justify; }}
 .abstract {{ font-size:9.3pt; margin:0 5mm 3pt; }}
 code, pre {{ font-family:"DejaVu Sans Mono","Menlo",monospace; font-size:7.6pt; }}
 pre {{ border:1px solid #000; padding:3pt 5pt; margin:2pt 0 3pt; white-space:pre-wrap; }}
 table {{ border-collapse:collapse; margin:2pt auto 1.5pt; font-size:8.3pt; }}
 th, td {{ border-top:1px solid #000; border-bottom:1px solid #000; padding:1pt 3.5pt; text-align:left; vertical-align:top; }}
 td.n, th.n {{ text-align:right; white-space:nowrap; }} .cap {{ font-size:8.2pt; text-align:center; margin:1pt 0 4pt; }}
 .refs p {{ text-align:left; padding-left:18pt; text-indent:-18pt; font-size:8.5pt; margin-bottom:1.6pt; }}
 .avoid {{ break-inside:avoid; }} .todo {{ background:#fff3a8; }}
</style></head><body>
<h1>An LLM Ranker over a Customer&rsquo;s Past and New Assets:<br>Implementing the Repeat-Aware Hybrid on FAR-Trans</h1>
<div class="meta">Student: Konstantin Patrushev &nbsp;&nbsp; Team: {esc(team['name'])} &nbsp;&nbsp; Email: kapatrushev@edu.hse.ru &nbsp;&nbsp; Date: 2026-11-25<br>
Repository: <a href="{REPO}">{REPO}</a> &nbsp;&nbsp; Experiment commit: <code>{esc(args.commit)}</code><br>
LLM4Rec project, Session 2 / Homework 2 &mdash; Implement and Test Your Idea (individual) &nbsp;&middot;&nbsp; Track: Hybrid</div>

<h2>Abstract</h2>
<p class="abstract">My Session 1 question asked whether an open-weight LLM ranker that orders a customer&rsquo;s past assets together with
never-bought candidates from an LLM embedding encoder improves nDCG@10 over the provided latest-buy baseline on FAR-Trans {c('fartrans')}.
I implemented the encoder (Qwen3-Embedding-0.6B), the ranker (Qwen3-1.7B, zero-shot, greedy) and their 2&times;2 ablation on the starter&rsquo;s
100-user protocol, with all four provided baselines. The hybrid scores nDCG@10 {f4(a3['ndcg_at_10'])} over all users and
{f4(a3['ndcg_at_10_nonempty'])} over the {a3['nonempty_truth_users']} users with purchases, against {f4(lb['ndcg_at_10'])} and
{f4(lb['ndcg_at_10_nonempty'])} for latest buy, with {fc.get('A3', 0)} invalid outputs and about {rnd(per_call['A3'], 1)} s per customer.
{esc(an['abstract_takeaway'])}</p>

<h2>1. Introduction</h2>
<p><b>Question and change.</b> FAR-Trans customers repeat earlier purchases often: in my Session 1 data profile 61% of the future
purchases of warm customers repeat an earlier buy, and latest buy (past assets newest first, then popular assets) was the strongest
provided baseline on the full warm cohort. The question is whether an LLM can do better than that rule at two jobs: proposing assets the
customer never bought (encoder) and ordering the customer&rsquo;s past and new candidates (ranker). The change plugs in after the starter&rsquo;s
data loading and before its evaluation: the same users, cutoff, eligible assets, truth and nDCG@10 code, with a different Top-10 list.</p>
<p><b>Contributions.</b> (i) A runnable implementation of the encoder, the ranker and the ablation arms with open-weight models;
(ii) a matched comparison with the four provided baselines, run times and failed cases; (iii) checks that the comparison is fair and
leak-free, and a hand check of one customer.</p>

<h2>2. Related Work</h2>
<p>LLMs can rank recommendation candidates zero-shot but struggle with the order of a history and show position and popularity bias
{c('llmrank')}; off-the-shelf LLM scores of repurchase candidates have lost to supervised rankers {c('cao26')}. Repeat purchases carry most
of the accuracy of sequential recommenders {c('li23')}. On FAR-Trans, FLARKO tunes Qwen3 models to generate three assets and reports
Hits@3 {c('flarko')}; I found no FAR-Trans study of a zero-shot LLM ranker against a recency baseline. The course provides an LLMRank-style
ranker over content-based candidates; my ranker differs in its candidate pool (the customer&rsquo;s own past assets plus never-bought
candidates) and its comparator (latest buy). Alternative considered: Mark Starchenko&rsquo;s team proposal of a logistic-regression ranker of
past assets, the classical control planned for the next session.</p>

<h2>3. Method</h2>
<p><b>Protocol (starter defaults).</b> The starter&rsquo;s deterministic 100 warm users, cutoff 2021-06-01, labels = Buys from 2021-06-01 to
2021-07-01 intersected with the 767 eligible assets, repeats allowed, binary nDCG@10 with empty truth counted as zero. My script imports the
starter&rsquo;s own functions; its user list equals the starter run&rsquo;s <code>protocol.json</code> (hash prefix
{h['protocol_hash_of_starter_run'][:12]}).</p>
<ul>
<li><b>Repeat channel.</b> The customer&rsquo;s eligible past Buy assets, newest first (ISIN breaks ties): exactly the latest-buy prefix.</li>
<li><b>Encoder E.</b> {esc(cfg['encoder']['model'])} (revision {cfg['encoder']['revision'][:8]}) embeds each eligible asset&rsquo;s as-of text
(name, short name, category, subcategory, sector, industry, market). Customer vector = Buy-count-weighted sum of their past assets&rsquo; vectors.
E re-scores the {cfg['encoder']['popular_pool']} most popular never-bought assets by cosine similarity and keeps the top
{cfg['encoder']['explore_candidates']} (the Session 1 pilot showed that similarity alone, without the popularity pool, loses to popularity).</li>
<li><b>Ranker R.</b> {esc(rk['model'])} (revision {rk['revision'][:8]}, resolved {str(rk.get('resolved_revision'))[:8]}), {esc(rk['dtype'])} on
{esc(rk['device'].upper())}, {esc(rk['decoding'])}, thinking disabled, at most {rk['max_new_tokens']} new tokens; torch {esc(rk['torch'])},
transformers {esc(rk['transformers'])}. The prompt (instruction below) holds group A, the up to {cfg['max_repeat_assets_in_prompt']} newest past
assets with Buy count, last Buy and last Sell dates, and group B, {cfg['encoder']['explore_candidates']} never-bought candidates with their
popularity rank. No profile, prices, amounts or truth. R returns ten ISINs; a list that is not exactly ten unique ISINs from the pool is
a failed case and the arm&rsquo;s rule list is used for that customer.</li>
<li><b>Arms.</b> A0 = latest buy (rule + popularity fill). A1 = rule + E fill (encoder only). A2 = R over group A + 10 popular never-bought
assets (ranker only). A3 = R over group A + E&rsquo;s 10 candidates (both). A1&minus;A0 isolates the encoder, A2&minus;A0 the ranker.</li>
</ul>
<pre>{esc(cfg['instruction'])}
{{"cutoff_date": "2021-06-01", "group_A_bought_before": [{{"ISIN", "name", "category", "subcategory", "sector", "industry", "market",
  "buy_count", "last_buy", "last_sell"}}, ...], "group_B_never_bought": [{{..., "popularity_rank"}}, ...]}}</pre>
<p><b>Hardware.</b> {esc(h['hardware']['platform'])} (Apple M5, 24 GB). Code: <code>src/hw2_hybrid.py</code>; generations with full prompts are
logged to <code>outputs/hw2/generations.jsonl</code> (customer IDs hashed; not committed).</p>

<h2>4. Experiments</h2>
<div class="avoid"><table>
<tr><th>Method</th><th class=n>Users</th><th class=n>Users with future purchases</th><th class=n>nDCG@10: all users</th>
<th class=n>nDCG@10: nonempty truth</th><th class=n>Runtime</th><th class=n>Failed cases</th></tr>
{table}</table>
<p class="cap">Table 1. Starter protocol, 100 users, cutoff 2021-06-01, 30 days (<code>hw2_metrics.json</code>). *The four provided baselines come
from one starter pass, timed together. A1: embedding all 767 assets once. A2/A3: LLM generation for 100 customers ({n0(tok['A2'][0])} and
{n0(tok['A3'][0])} prompt tokens, {n0(tok['A2'][1])} and {n0(tok['A3'][1])} output tokens); A3 includes the embedding time. Failed cases fall back to
the rule list and are included in the scores.</p></div>
<p><b>Beyond the demo.</b> The 100-user sample has only {lb['nonempty_truth_users']} customers with purchases. On all
{n0(W['latest_buy']['users'])} warm customers ({n0(W['latest_buy']['nonempty_truth_users'])} with purchases) the encoder-only arm A1 scores
{f4(W['A1_rule_encoder_fill']['ndcg_at_10_nonempty'])} on customers with purchases against {f4(W['latest_buy']['ndcg_at_10_nonempty'])} for latest buy
(<code>hw2_rule_only_10404users.json</code>): the small demo gain of A1 does not hold at scale. The LLM arms were not run on the full cohort
(about {rnd(per_call['A3'] * W['latest_buy']['users'] / 3600, 1)} h per arm at the measured speed).</p>
<p><b>What changed per customer.</b> {an['changes_text']}</p>
<p><b>Checks.</b> (a) For all 100 customers A0 equals the starter&rsquo;s latest-buy list and the four baselines&rsquo; nDCG@10 equal the starter&rsquo;s
<code>metrics.json</code> exactly (assertions in the script). (b) Every date in every prompt precedes the cutoff (assertion); labels are computed
only after all lists are fixed. (c) {esc(an['hand_check_text'])}</p>

<h2>5. Discussion</h2>
<p><b>What improved and what failed.</b> {an['discussion_text']}</p>
<p><b>Next experiment.</b> Keep the users, cutoff, pool and prompt fixed and change one thing: run A2/A3 on a validation cutoff (1 January 2021)
and on the full warm cohort to get more than {lb['nonempty_truth_users']} labelled customers, with three shuffled candidate orders to measure position
sensitivity, next to the team&rsquo;s logistic-regression ranker of past assets as the same-information classical control.</p>
<p><b>Team discussion and individual contribution.</b> {esc(team['documented'])} <span class="todo">{esc(team['todo'])}</span></p>
<ul><li><b>My work:</b> {esc(team['mine'])}</li><li><b>Shared:</b> {esc(team['shared'])}</li></ul>

<h2>6. AI Usage Disclosure</h2>
<p><b>Tools.</b> Claude Code 2.1.292 (VS Code extension) with Claude Opus 5.5, one session. <b>Use.</b> Code for the experiment and the report
builder, running the models and the starter, analysis, and a draft of this report; every number is rendered from <code>evidence/</code>.
<b>What I personally verified.</b> <span class="todo">{esc(team['verified'])}</span> <b>Trusted without verification.</b>
<span class="todo">{esc(team['trusted'])}</span> <b>Session log.</b> <code>patrushev_konstantin_session2_session.json</code>, a derived export of the
unmodified session lines of this homework (xz + base64 inside JSON, because the LMS rejects the raw log; SHA-256 and a restore command inside).</p>

<h2>References</h2><div class="refs">{refs}</div>
</body></html>"""
    REP.mkdir(exist_ok=True)
    (REP / "report_session2.html").write_text(doc, encoding="utf-8")
    print("report_session2.html written")
    if args.pdf:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={REP / PDF_NAME}", (REP / "report_session2.html").as_uri()], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("pdf:", REP / PDF_NAME)


USED = ["fartrans", "llmrank", "cao26", "li23", "flarko"]

if __name__ == "__main__":
    main()
