"""Render report/report.html (and the PDF) from evidence files. Every number comes from evidence/.

Run: .venv/bin/python -I src/build_report.py [--pdf]
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
PDF_NAME = "patrushev_konstantin_session1_report.pdf"


def j(name):
    return json.loads((EV / name).read_text())


def rnd(x, d):
    return str(Decimal(str(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def f3(x):
    return rnd(x, 3)


def f4(x):
    return rnd(x, 4)


def pct(x, d=0):
    return rnd(100 * x, d) + "%"


def n0(x):
    return f"{int(x):,}"


def esc(s):
    return html.escape(str(s))


PIPELINE_SVG = """<svg viewBox="0 0 700 150" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;font-family:'Times New Roman',serif">
<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#000"/></marker></defs>
<g font-size="11" fill="#000" stroke="#000">
<rect x="4" y="8" width="150" height="40" fill="none"/><text x="79" y="25" text-anchor="middle" stroke="none">Past Buy/Sell events</text><text x="79" y="40" text-anchor="middle" stroke="none">(dates, counts) before cutoff</text>
<rect x="4" y="96" width="150" height="40" fill="none"/><text x="79" y="113" text-anchor="middle" stroke="none">As-of asset text: name +</text><text x="79" y="128" text-anchor="middle" stroke="none">category, sector, market</text>
<rect x="196" y="8" width="160" height="40" fill="none"/><text x="276" y="25" text-anchor="middle" stroke="none">REPEAT channel: past assets,</text><text x="276" y="40" text-anchor="middle" stroke="none">newest first (= latest buy)</text>
<rect x="196" y="96" width="160" height="40" fill="none" stroke-dasharray="4 2"/><text x="276" y="113" text-anchor="middle" stroke="none">E: embedding encoder</text><text x="276" y="128" text-anchor="middle" stroke="none">top-20 never-bought assets</text>
<rect x="398" y="52" width="150" height="44" fill="none" stroke-dasharray="4 2"/><text x="473" y="70" text-anchor="middle" stroke="none">R: LLM ranker orders</text><text x="473" y="86" text-anchor="middle" stroke="none">repeat + explore pool</text>
<rect x="590" y="52" width="104" height="44" fill="none"/><text x="642" y="70" text-anchor="middle" stroke="none">Top-10 list,</text><text x="642" y="86" text-anchor="middle" stroke="none">nDCG@10</text>
<line x1="154" y1="28" x2="194" y2="28" marker-end="url(#a)"/><line x1="154" y1="116" x2="194" y2="116" marker-end="url(#a)"/>
<line x1="154" y1="40" x2="194" y2="104" marker-end="url(#a)"/>
<line x1="356" y1="28" x2="396" y2="62" marker-end="url(#a)"/><line x1="356" y1="116" x2="396" y2="86" marker-end="url(#a)"/>
<line x1="548" y1="74" x2="588" y2="74" marker-end="url(#a)"/>
</g></svg>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true")
    args = ap.parse_args()

    prof = j("data_profile.json")["cutoffs"]
    d = prof["2021-06-01"]
    w = d["warm_cohort"]
    pil = j("pilot_headroom.json")
    ex = j("data_example.json")
    lit = j("literature.json")
    bd, bw = j("baseline_demo100_metrics.json"), j("baseline_warm_all_metrics.json")
    pd_, pw_ = j("baseline_demo100_protocol_summary.json"), j("baseline_warm_all_protocol_summary.json")
    team = j("team.json")
    PW, PD = pil["warm_all"], pil["demo_100"]
    M = lambda r, k: r["methods"][k]
    LB = "latest_buy (repeat newest-first + popularity fill)"
    lbw = M(PW, LB)["ndcg_at_10_nonempty"]
    or_split = M(PW, "oracle split: repeat newest-first + popularity explore")["ndcg_at_10_nonempty"]
    or_rep = M(PW, "oracle order inside repeat channel + popularity fill")["ndcg_at_10_nonempty"]
    freq_w = M(PW, "repeat ordered by buy count, then recency + popularity fill")["ndcg_at_10_nonempty"]
    freq_d = M(PD, "repeat ordered by buy count, then recency + popularity fill")["ndcg_at_10_nonempty"]
    lbd = M(PD, LB)["ndcg_at_10_nonempty"]
    rec = PW["explore_recall_of_never_bought_purchases"]
    pop_w = bw["methods"]["popularity"]["ndcg_at_10_nonempty"]
    shares = [prof[c]["warm_cohort"]["share_repeat_items"] for c in prof]
    lc = ex["leakage_checks"]
    lq = lc["asof_profiles_at_cutoff_with_lastQuestionnaireDate_on_or_after_cutoff"]
    lp = lc["limit_prices_rows_whose_series_ends_on_or_after_cutoff (profitability spans the future)"]
    r = ex["record_shown"]
    pr, ar = ex["asof_profile_row"], ex["asof_asset_row"]

    # ---- Table: baselines and pilot (what was run)
    def row(name, rd, rw, ref=""):
        return (f"<tr><td>{name}{ref}</td><td class=n>{f4(rd['ndcg_at_10'])}</td><td class=n>{f4(rd['ndcg_at_10_nonempty'])}</td>"
                f"<td class=n>{f4(rw['ndcg_at_10'])}</td><td class=n>{f4(rw['ndcg_at_10_nonempty'])}</td></tr>")
    base_rows = "".join(row(lab, bd["methods"][k], bw["methods"][k]) for lab, k in
                        [("Popularity", "popularity"), ("CBF (starter tokens)", "cbf"),
                         ("Latest buy", "latest_buy"), ("Latest buy or sell", "latest_buy_or_sell")])
    pilot_rows = "".join(row(lab, M(PD, k), M(PW, k)) for lab, k in [
        ("Repeat channel + CBF-token explore fill", "repeat + CBF-token explore fill"),
        ("Repeat channel + TF-IDF-text explore fill (encoder control)", "repeat + TF-IDF-text explore fill"),
        ("Repeat channel + recent-popularity (90 d) fill", "repeat + recent-popularity (90 days) explore fill"),
        ("Repeat channel by buy count, then recency", "repeat ordered by buy count, then recency + popularity fill")])
    oracle_rows = "".join(row(lab, M(PD, k), M(PW, k)) for lab, k in [
        ("Oracle: best per-user repeat/explore split (popularity)", "oracle split: repeat newest-first + popularity explore"),
        ("Oracle: perfect order inside the repeat channel", "oracle order inside repeat channel + popularity fill")])

    lit_rows = "".join(
        f"<tr><td>{esc(x['short'])} [{x['n']}]</td><td>{esc(x['method'])}</td><td>{esc(x['data'])}</td><td>{esc(x['limit'])}</td></tr>"
        for x in lit["table"])
    refs = "".join(f"<p>[{x['n']}] {x['ieee']}</p>" for x in lit["references"])
    R = {x["key"]: x["n"] for x in lit["references"]}

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Session 1 Report &mdash; Repeat or Explore on FAR-Trans</title>
<style>
 a {{ color:#000; text-decoration:none; }}
 @page {{ size:A4; margin:12mm 13mm; }}
 body {{ font-family:"Times New Roman","Liberation Serif",serif; font-size:9.7pt; line-height:1.22; color:#000; margin:0; }}
 h1 {{ font-size:14pt; text-align:center; margin:0 0 4pt; line-height:1.2; }}
 .meta {{ text-align:center; font-size:9.3pt; margin-bottom:5pt; }}
 h2 {{ font-size:10.4pt; margin:5pt 0 2pt; text-transform:uppercase; letter-spacing:.3pt; break-after:avoid; }}
 h3 {{ font-size:9.9pt; margin:3.5pt 0 1.5pt; font-style:italic; font-weight:normal; break-after:avoid; }}
 p {{ margin:0 0 2.8pt; text-align:justify; }}
 ul {{ margin:0 0 2.8pt; padding-left:14pt; }} li {{ margin-bottom:.8pt; text-align:justify; }}
 .abstract {{ font-size:9.3pt; margin:0 5mm 3pt; }}
 code, pre {{ font-family:"DejaVu Sans Mono","Menlo",monospace; font-size:7.6pt; }}
 pre {{ border:1px solid #000; padding:3pt 5pt; margin:2pt 0 3pt; white-space:pre-wrap; }}
 table {{ border-collapse:collapse; margin:2pt auto 1.5pt; font-size:8.2pt; }}
 th, td {{ border-top:1px solid #000; border-bottom:1px solid #000; padding:1pt 3.5pt; text-align:left; vertical-align:top; }}
 th {{ font-weight:bold; }} td.n, th.n {{ text-align:right; white-space:nowrap; }}
 table.lit {{ font-size:7.8pt; width:100%; }}
 .cap {{ font-size:8.2pt; text-align:center; margin:1pt 0 4pt; }}
 .refs p {{ text-align:left; padding-left:18pt; text-indent:-18pt; font-size:8.5pt; margin-bottom:1.6pt; }}
 .avoid {{ break-inside:avoid; }}
 .todo {{ background:#fff3a8; }}
</style></head><body>

<h1>Repeat or Explore? A Study Plan for a Hybrid LLM Encoder&ndash;Ranker<br>on FAR-Trans Financial Asset Recommendation</h1>
<div class="meta">Student: Konstantin Patrushev &nbsp;&nbsp; Team: <span class="{'' if team['name'] else 'todo'}">{esc(team['name'] or '[team name]')}</span> &nbsp;&nbsp; Date: 2026-11-18 &nbsp;&nbsp; Email: kapatrushev@edu.hse.ru<br>
LLM4Rec project, Session 1 &mdash; Research Question and Minimal Study Plan (individual) &nbsp;&middot;&nbsp; Track: Hybrid &nbsp;&middot;&nbsp; State: planned; a classical pilot (no LLM) was run</div>

<h2>Abstract</h2>
<p class="abstract">In FAR-Trans [{R['fartrans']}], {pct(w['share_repeat_items'])} of the future purchases of customers with a purchase history repeat an asset
they already bought, and on the full warm cohort a list of their past buys ordered by recency (&ldquo;latest buy&rdquo;) is the strongest of the
course&rsquo;s classical baselines (nDCG@10 {f3(lbw)} for the {n0(w['nonempty_truth_users'])} customers with a purchase in the label window, against {f3(pop_w)} for popularity).
I plan a hybrid in which an open-weight embedding encoder proposes never-bought assets and an open-weight LLM ranker orders the customer&rsquo;s
past assets together with those proposals, compared with latest buy in a 2&times;2 encoder/ranker ablation with same-information classical controls.
A pilot without any LLM shows where the headroom is: a perfect order inside the past assets would raise nDCG@10 from {f3(lbw)} to {f3(or_rep)},
whereas the best per-user split between past and new assets reaches only {f3(or_split)}. The ranker&rsquo;s ordering of known assets, not the
discovery of new ones, is therefore the first thing an LLM must improve, and the design reports a negative or null result just as clearly.</p>

<h2>1. Introduction</h2>
<p><b>Problem.</b> The shared task ranks ten assets per customer and scores the list by nDCG@10 against the assets the customer actually
buys in a later window. The official item scope, split and evaluated users are still pending; until they are frozen I assume the course
starter&rsquo;s teaching protocol: cutoff 1 June 2021, a 30-day label window, customers with at least one earlier Buy (&ldquo;warm&rdquo;), the
{n0(d['eligible_assets'])} assets with as-of metadata and a positive past price, repeat purchases allowed. Under it the full warm cohort has
{n0(d['warm_users'])} customers, of whom {n0(w['nonempty_truth_users'])} buy something in the window; the repeat share was
{pct(min(shares))}&ndash;{pct(max(shares))} at four cutoffs between June 2020 and January 2022 (<code>data_profile.json</code>). The original
FAR-Trans protocol is different: it ranks only assets the customer has not bought and drops repurchases from the test set [{R['fartrans']}], so
numbers under the two protocols are not comparable.</p>
<p><b>Research question.</b> <i>We test whether a repeat-aware LLM hybrid &mdash; an open-weight embedding encoder that proposes
never-bought assets plus an open-weight LLM ranker that orders the customer&rsquo;s past assets together with those proposals &mdash; improves
nDCG@10 over the latest-buy baseline for warm FAR-Trans customers at the shared cutoff.</i> Intervention: the encoder&ndash;ranker hybrid.
Outcome: nDCG@10 over all evaluated customers (empty truth counts as zero), with the mean over customers with purchases reported
separately. Comparator: latest buy (past buys newest first, filled with popular assets), which uses the same past events and asset
metadata. Population: warm customers at the shared cutoff. Track: Hybrid; status: planned, with a classical pilot already run (§4).</p>
<p><b>Research importance.</b> In e-commerce, repeat purchases carry most of the accuracy of sequential recommenders while
exploration stays hard [{R['li23']}], and dedicated repeat modules are strong [{R['repeatnet']}], [{R['trex']}]. LLM rankers struggle with the
order of a history and show position and popularity bias [{R['llmrank']}], and off-the-shelf LLM scores of repurchase candidates have lost to
supervised rankers [{R['cao26']}]. Whether an LLM adds anything on top of a strong recency rule in financial transactions, and through which
component &mdash; proposing new assets (encoder) or ordering known ones (ranker) &mdash; is open. The study separates the two, so even a null
result locates where LLM capacity does not help on this kind of data.</p>
<p><b>Business value.</b> The stakeholder is the product owner of a bank&rsquo;s investment app who decides whether the &ldquo;your assets&rdquo;
module keeps the latest-buy rule or moves to the hybrid, and whether a slot for never-bought assets is worth showing. The decision needs the
measured ranking gain next to the measured inference time per customer. The decision must not rest on user reactions alone, because users of
LLM financial advisors appeared insensitive to the quality of advice [{R['takayanagi25']}], and purchase-based metrics are not profitability:
the FAR-Trans authors report the two negatively correlated [{R['tois26']}]. The study therefore makes no claim about returns or suitability.</p>

<h2>2. Related Work</h2>
<table class="lit avoid"><tr><th style="width:17%">Study</th><th style="width:25%">Method</th><th style="width:26%">Data and evaluation</th><th>Limitations and connection to my question</th></tr>
{lit_rows}</table>
<p><b>Nearest prior work.</b> {lit['nearest']}</p>
<p><b>Gap.</b> {lit['gap']}</p>
<p><b>Alternatives considered.</b> (i) The course&rsquo;s example topics &mdash; LLM paraphrases of asset descriptions and LLM reranking of
content-based candidates &mdash; were excluded on the instructor&rsquo;s instruction not to reuse the baseline topics. (ii) A profile-aware
ranker (risk level, investment capacity): {pct((d['profile_status_warm']['riskLevel'].get('estimated', 0) + d['profile_status_warm']['riskLevel'].get('missing', 0)) / d['warm_users'], 0)} of warm
risk levels are estimated or missing, and using the profile would require the same profile for every control; left for later. (iii) Price
momentum as an input: pre-cutoff prices are allowed, but the question would shift from recommendation to market timing.</p>

<h2>3. Method</h2>
<h3>3.1 One actual record and its fields</h3>
<pre>source: FAR-Trans public release [{R['dataset']}], University of Glasgow, transactions.csv   record id: transactionID {r['transactionID']}
fields: customerID, ISIN, transactionID, transactionType, timestamp, totalValue, units, channel, marketID
values: {r['customerID']}, {r['ISIN']}, {r['transactionID']}, {r['transactionType']}, {r['timestamp']}, {r['totalValue']}, {r['units']}, {r['channel']}, {r['marketID']}
window: history (before the cutoff {ex['cutoff']}); the customer is in the starter's 100-user demo cohort and has no transaction on or after the cutoff</pre>
<p>The customer ID is a pseudonymous hash, truncated here. <b>Observed</b> at 2021-05-28: transactionType, timestamp, ISIN, marketID (used),
totalValue, units and channel (not used: the plan reads no amounts and no sales channel). The as-of profile row (timestamp {pr['timestamp']}) has customerType
{pr['customerType']} (observed), riskLevel {pr['riskLevel']} and investmentCapacity {pr['investmentCapacity']} (both <b>estimated</b> by the bank&rsquo;s
model) and lastQuestionnaireDate {pr['lastQuestionnaireDate']}, a placeholder, i.e. <b>missing</b>; the profile is not an input of any compared
method. The as-of asset row (timestamp {ar['timestamp']}) gives the name &ldquo;{esc(ar['assetName'])}&rdquo;, category {ar['assetCategory']},
subcategory {ar['assetSubCategory']}, market {ar['marketID']} (observed) and no sector or industry (missing); these fields form the encoder text.
<b>Leakage check.</b> lastQuestionnaireDate lies on or after the cutoff in {n0(lq['count'])} of {n0(lq['of'])} as-of profiles, and the
<code>profitability</code> column of <code>limit_prices.csv</code> uses prices up to a series end after the cutoff for {n0(lp['count'])} of
{n0(lp['of'])} assets: both are future information and are excluded. Rows dated on or after the cutoff are never inputs; only Buys in the window
become labels (<code>data_example.json</code>).</p>

<h3>3.2 Planned comparison</h3>
<div class="avoid">{PIPELINE_SVG}
<p class="cap">Fig. 1. Planned hybrid. Dashed boxes are the two LLM components; replacing either by its classical counterpart gives the ablation.</p></div>
<ul>
<li><b>Control (A0).</b> Latest buy: past assets newest first, the remaining slots filled by popularity. Same inputs as the hybrid: dated past
Buy/Sell events, Buy counts and as-of asset metadata; no profile, prices or amounts for any method.</li>
<li><b>Encoder (E).</b> {esc(lit['models']['encoder'])} embeds the text of every eligible asset; a customer vector is the Buy-count-weighted sum of the
vectors of their past assets; the 20 most similar never-bought assets form the explore candidates.</li>
<li><b>Ranker (R).</b> {esc(lit['models']['ranker'])}, greedy decoding with thinking disabled, receives the dated events of the repeat channel and
the explore candidates and returns ten unique ISINs from that pool. An invalid answer falls back to the control&rsquo;s list; fallbacks are
counted and reported separately from valid outputs.</li>
<li><b>Contribution check (2&times;2).</b> A0 = rule + popularity explore; A1 = rule + E (encoder only); A2 = R + popularity explore (ranker only);
A3 = R + E (both). A1&minus;A0 isolates the encoder, A2&minus;A0 the ranker, A3 versus A1 and A2 their interaction.</li>
<li><b>Same-information controls.</b> C1: TF-IDF over the identical asset text instead of E (already run, §4); C2: a classical learned ranker
(LightGBM LambdaRank [{R['lightgbm']}]) over the features the LLM sees (days since last Buy and Sell, Buy count, explore similarity, popularity),
trained on an earlier cutoff only; C3: past assets ordered by Buy count (already run). If A2 beats A0 but not C2, the gain comes from the
information, not the LLM &mdash; the outcome reported for groceries in [{R['cao26']}].</li>
<li><b>Contamination check.</b> Asset names are real, and both models were released in 2025 [{R['qwen3emb']}], [{R['qwen3']}], so their pretraining
data may cover events after the 2021 cutoff. A3 is repeated with names replaced by neutral tokens; a large drop flags possible look-ahead
through pretraining.</li>
<li><b>Measures.</b> nDCG@10 (all customers; customers with purchases and their count) to four decimals, also split into customers whose
window purchases are only repeats versus those with new assets, as [{R['li23']}] advise; explore recall@10 for the encoder; the ranker&rsquo;s
invalid-output rate; end-to-end recommendation time per customer, which also breaks benchmark ties; hardware.</li>
<li><b>Variance.</b> Greedy decoding is deterministic for a fixed prompt, but LLM rankers depend on candidate order [{R['llmrank']}]: R runs
with three shuffled candidate orders and the spread is reported; differences to A0 get a paired per-customer bootstrap interval as a
descriptive range. No LLM acts as a judge: the only ground truth is observed purchases.</li>
<li><b>Feasibility.</b> Session 2: freeze the protocol, implement A0&ndash;A3 and C1 on the 100-user demo and measure time per customer.
Session 3: (optional RAG) richer retrieved context for R. Session 4: (optional) LoRA tuning of R on earlier cutoffs only. Session 5: the
full warm cohort and a second cutoff, ablations, failure analysis. Session 6: defence. Compute: Apple M5 laptop (24 GB, MPS) or a cloud GPU;
E embeds {n0(d['eligible_assets'])} assets once, R makes one call per evaluated customer ({n0(pd_['users'])} for the demo,
{n0(pw_['users'])} for the warm cohort). A practical bottleneck: on my connection the encoder weights (1.19 GB) downloaded from the Hugging Face
CDN at about 72 KB/s, so the weights will be fetched once in advance or the runs moved to a cloud runtime.</li>
<li><b>Risks.</b> Ethics: the output is not investment advice and nDCG@10 is not suitability or profit. Privacy: pseudonymous IDs only,
no re-identification, aggregates published, raw customer IDs not committed. Contamination: as above. Small samples: the demo has only
{bd['methods']['popularity']['nonempty_truth_users']} customers with purchases (§4).</li>
</ul>

<h2>4. Experiments</h2>
<p>Only classical components were run: the four starter baselines and a pilot that reuses the starter&rsquo;s loading rules, with no LLM.
The LLM encoder and ranker are planned; no LLM number appears in this report.</p>
<div class="avoid"><table>
<tr><th>Method (no LLM)</th><th class=n>Demo: all</th><th class=n>Demo: with purchases</th><th class=n>Warm: all</th><th class=n>Warm: with purchases</th></tr>
{base_rows}{pilot_rows}{oracle_rows}
</table>
<p class="cap">Table 2. nDCG@10, cutoff 2021-06-01, 30-day window. Demo = the starter&rsquo;s 100 users ({bd['methods']['popularity']['nonempty_truth_users']} with
purchases); warm = all {n0(pw_['users'])} warm customers ({n0(bw['methods']['popularity']['nonempty_truth_users'])} with purchases). The starter&rsquo;s
<code>protocol_hash</code> prefixes are {pd_['protocol_hash'][:12]} and {pw_['protocol_hash'][:12]}. Oracle rows use the labels and are upper bounds,
not methods. Files: <code>baseline_*_metrics.json</code>, <code>pilot_headroom.json</code>.</p></div>
<p><b>What the pilot says.</b> (a) The recency rule is hard to beat with simple changes: replacing its popularity fill by CBF tokens, TF-IDF text
or recent popularity does not raise the warm-cohort score. (b) The headroom sits inside the repeat channel: the oracle order of past assets
reaches {f3(or_rep)} against {f3(lbw)}, while the best repeat/explore split reaches {f3(or_split)}. (c) For never-bought purchases, popularity
finds {pct(rec['popularity@10']['recall'])} in its top 10 (recent popularity {pct(rec['recent popularity 90d@10']['recall'])}, TF-IDF text
{pct(rec['TF-IDF text@10']['recall'])}, CBF tokens {pct(rec['CBF tokens@10']['recall'])}) &mdash; the bar the LLM encoder must clear.
(d) The demo slice is too small to rank methods: ordering past assets by Buy count beats latest buy on the demo ({f3(freq_d)} vs {f3(lbd)})
but loses on the warm cohort ({f3(freq_w)} vs {f3(lbw)}). The planned evaluation therefore reports the demo, as the course requires, and the
full warm cohort as the main comparison.</p>

<h2>5. Discussion</h2>
<p><b>Team discussion.</b> <span class="todo">{esc(team['discussion'])}</span></p>
<ul>
<li><b>Options considered.</b> <span class="todo">{esc(team['options'])}</span></li>
<li><b>Agreement and unresolved differences.</b> <span class="todo">{esc(team['agreement'])}</span></li>
<li><b>My contribution.</b> <span class="todo">{esc(team['contribution'])}</span></li>
<li><b>My position and reasons.</b> I adopt the repeat-aware hybrid because the pilot locates the headroom in the ordering of known assets
(oracle +{f3(or_rep - lbw)}) and only a small part in exploration (+{f3(or_split - lbw)}), so a design that tests the two LLM components
separately can explain either outcome.</li>
</ul>
<p><b>Threats to validity.</b> The protocol is still pending and may change the cohort; {bd['methods']['popularity']['nonempty_truth_users']} labelled
customers in the demo cannot rank methods; pretraining may leak post-cutoff knowledge through asset names; LLM rankers have position bias
and can return invalid lists; the oracle bounds are not achievable targets.</p>
<p><b>Meaning of the outcomes.</b> If A2 or A3 beats A0 and C2, an LLM adds ordering skill beyond the information it is given. If only A1
helps, the value is in proposing new assets. If no variant beats A0, the recency rule is sufficient for this data, which is a useful negative
result for the product decision in &sect;1.</p>

<h2>6. AI Usage Disclosure</h2>
<p><b>AI tools used.</b> Claude Code 2.1.292 (VS Code extension) with Claude Opus 5.5, one session, including a sub-agent for the literature
search and reference checks.</p>
<p><b>How AI was used.</b> Code (data profile, pilot, leakage checks, report builder), running the starter, literature search and verification
through Crossref and arXiv, and a draft of this report; every number is rendered from <code>evidence/</code> by <code>src/build_report.py</code>.</p>
<p><b>What I personally verified.</b> <span class="todo">{esc(team['verified'])}</span></p>
<p><b>What I trusted without verification.</b> <span class="todo">{esc(team['trusted'])}</span></p>
<p><b>Session log.</b> <code>patrushev_konstantin_session1_session.json</code> is a derived export: the unmodified lines of the Claude Code
session from the first message of this homework to its end (the same session earlier held the midterm), stored xz-compressed and
base64-encoded because the LMS rejects the raw log, with SHA-256 values and a restore command inside.</p>

<h2>References</h2>
<div class="refs">{refs}</div>
</body></html>
"""
    REP.mkdir(exist_ok=True)
    (REP / "report.html").write_text(doc, encoding="utf-8")
    print("report.html written")
    if args.pdf:
        out = REP / PDF_NAME
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", (REP / "report.html").as_uri()], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("pdf:", out)


if __name__ == "__main__":
    main()
