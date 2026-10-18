# Numbers

Every number that appears in the README, the demo or an email, and where it comes from.

All numbers are on synthetic packets with planted issues. The generator plants issues and look-alikes at rates set in `generator/settings.py`; those are planting rates, not industry rates, and nothing here implies a real fraud rate or real savings. Seeds: 1, 2, 3, 4, 5, 500 packets each. Thresholds were tuned on dev seeds 101-102 only.

These are the report seeds (1-5). They were never used to tune anything.

Decision code and thresholds (`payhold/`, `config/`, `pyproject.toml`, `uv.lock`) unchanged since freeze commit `edc7b13a3ffeae171321a27a45649507a91c201a` (`results/freeze.txt`).

Produced by `make eval` (`eval/run.py`, `eval/report.py`); raw decisions in `results/decisions.json`.

## Headline

| Number | What it measures | Baseline | payhold | Single run or aggregate | Runs / seeds | n | Raw output |
|---|---|---|---|---|---|---|---|
| Bad-packet exposure paid out, per seed | Sum of `exposure_usd` on planted-issue packets that got "pay" | $137,000 ($133,500-$148,325) | $0 ($0-$0) | aggregate: median (min-max) across seeds | 5 seeds x 500 | 425 planted-issue packets | `results/decisions.json` |
| Planted exposure, per seed (context) | Sum of `exposure_usd` on all planted-issue packets | $187,600 ($181,750-$195,650) | same | aggregate: median (min-max) across seeds | 5 seeds x 500 | 425 | `results/decisions.json` |
| Clean packets paid straight through: plain clean | Paid / total. | 100.0% (100.0-100.0%) | 100.0% (100.0-100.0%) | aggregate: median (min-max) across seeds | 5 seeds x 500 | 1,775 | `results/decisions.json` |
| Clean packets paid straight through: seen look-alikes | Paid / total. Designed by the same author before the freeze. | 100.0% (100.0-100.0%) | 100.0% (100.0-100.0%) | aggregate: median (min-max) across seeds | 5 seeds x 500 | 300 | `results/decisions.json` |
| Clean packets paid straight through: held-out look-alikes | Paid / total. Separate stream implemented after the freeze commit; decision code, thresholds and dependencies unchanged since. Each packet decided independently against the end-of-stream snapshot. | 100.0% (100.0-100.0%) | 100.0% (100.0-100.0%) | aggregate: median (min-max) across seeds | 5 seeds x 50 | 250 | `results/decisions.json` |
| Held-out kind: DBA name on BOL/POD | Paid / total, this kind only | 100.0% (100.0-100.0%) | 100.0% (100.0-100.0%) | aggregate: median (min-max) across seeds | 5 seeds x 25 | 125 | `results/decisions.json` |
| Held-out kind: same load number, different broker (confirms key scoping) | Paid / total, this kind only | 100.0% (100.0-100.0%) | 100.0% (100.0-100.0%) | aggregate: median (min-max) across seeds | 5 seeds x 25 | 125 | `results/decisions.json` |
| Duplicate payouts (a) | Rail attempts per load, 50 concurrent distinct requests for one load, rail dedupe off, DynamoDB Local | no payout step | 1 in every trial | aggregate: min-max across trials | 100 trials | 100 loads | `results/payout_trials.json` |
| Duplicate payouts (b) | Rail attempts per load, 50 concurrent copies of one request, rail dedupe off, DynamoDB Local | no payout step | 1 in every trial | aggregate: min-max across trials | 100 trials | 100 loads | `results/payout_trials.json` |
| Duplicate payouts (c) | Crash after the rail call, clock past the lease, retry | no payout step | 2 attempts, 1 send in every trial | aggregate across trials | 100 trials | 100 loads | `results/payout_trials.json` |
| Read-then-write control | Scenario (a) with the conditional write replaced by read-then-write. A race, so it varies run to run | no payout step | 5-37 rail attempts per load | single run of 100 trials, min-max | 100 trials | 100 loads | `results/payout_naive_control.json` |
| Extraction round-trip | Every extracted field vs the generator's spec, seed 1 and dev seeds 101-102 | no separate extractor | 0 failures in 54,000 field checks | aggregate over 3 seeds | 3 seeds x 500 packets x 3 PDFs | 54,000 fields | `results/roundtrip.txt` (`make roundtrip`) |

Decision latency is in [`latency.md`](latency.md) (timings are kept out of this file so it stays byte-identical across runs).

## Money shot (seed 1, single run)

Numbers shown on the page and in `docs/demo.gif`, exported to `web/public/data/seed1.json` by `make eval`. Single run of seed 1, on synthetic packets with planted issues.

| Number | Baseline | payhold |
|---|---|---|
| Packets replayed | 500 | 500 |
| Bad-packet exposure paid out | $148,325 | $0 |
| Clean packets paid straight through (plain and seen look-alikes) | 415 / 415 | 415 / 415 |

Featured packet: request S1-0004, the first double-factoring follower in seed 1 that the baseline paid and payhold held. Load 9086253 arrives through Cobalt Receivables 35 synthetic minutes after Alder Funding asked to pay it (request S1-0001); exposure $1,725. Reason line, from the decision record: `load 9086253 from broker USDOT 99684502 already requested through Alder Funding at 2026-03-02T06:07:00Z (request S1-0001)`

## Per seed

| Seed | Planted exposure | Paid out: baseline | Paid out: payhold | Plain clean paid: baseline | Plain clean paid: payhold | Seen look-alikes paid: baseline | Seen look-alikes paid: payhold |
|---|---|---|---|---|---|---|---|
| 1 | $195,650 | $148,325 | $0 | 355/355 | 355/355 | 60/60 | 60/60 |
| 2 | $183,200 | $137,000 | $0 | 355/355 | 355/355 | 60/60 | 60/60 |
| 3 | $181,750 | $133,500 | $0 | 355/355 | 355/355 | 60/60 | 60/60 |
| 4 | $189,900 | $138,750 | $0 | 355/355 | 355/355 | 60/60 | 60/60 |
| 5 | $187,600 | $136,575 | $0 | 355/355 | 355/355 | 60/60 | 60/60 |

## Detection by issue type

Coverage check: issue types the generator plants, checks written by the same author. Packets held, all report seeds pooled (5 seeds x 500).

| # | Issue type | n | Baseline held | payhold held |
|---|---|---|---|---|
| 1 | padding | 100 | 100 (100.0%) | 100 (100.0%) |
| 2 | duplicate_rebill | 75 | 75 (100.0%) | 75 (100.0%) |
| 3 | double_factoring | 100 | 0 (0.0%) | 100 (100.0%) |
| 4 | bank_change | 75 | 0 (0.0%) | 75 (100.0%) |
| 5 | double_brokering | 75 | 0 (0.0%) | 75 (100.0%) |

## Held-out look-alikes

| Seed | Kind | n | Paid: baseline | Paid: payhold | payhold hold reasons |
|---|---|---|---|---|---|
| 1 | DBA name on BOL/POD | 25 | 25 | 25 | none |
| 1 | same load number, different broker (confirms key scoping) | 25 | 25 | 25 | none |
| 2 | DBA name on BOL/POD | 25 | 25 | 25 | none |
| 2 | same load number, different broker (confirms key scoping) | 25 | 25 | 25 | none |
| 3 | DBA name on BOL/POD | 25 | 25 | 25 | none |
| 3 | same load number, different broker (confirms key scoping) | 25 | 25 | 25 | none |
| 4 | DBA name on BOL/POD | 25 | 25 | 25 | none |
| 4 | same load number, different broker (confirms key scoping) | 25 | 25 | 25 | none |
| 5 | DBA name on BOL/POD | 25 | 25 | 25 | none |
| 5 | same load number, different broker (confirms key scoping) | 25 | 25 | 25 | none |

What the DBA kind actually tests: in 123 of 125 DBA packets the BOL name does not match the rate con name after normalization (eval-side probe, not a decider). payhold passes them because the name check also accepts the DBA in the carrier registry. That rule was written before the freeze, but the plan already said carriers have DBAs, so this row is weaker evidence than a truly unseen look-alike would be. See `docs/design-notes.md`.
