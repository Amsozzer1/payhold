"""Writes results/numbers.md from the raw outputs. No timings here; those go to latency.md."""

from __future__ import annotations

import json
from pathlib import Path

from eval import metrics as m

CAVEAT = "on synthetic packets with planted issues"


def usd(cents: float) -> str:
    return f"${round(cents / 100):,}"


def pct(num: int, den: int) -> str:
    return f"{100 * num / den:.1f}%"


def rate_row(per_seed: list[tuple[int, int]]) -> tuple[str, str]:
    rates = [p / n for p, n in per_seed]
    med, lo, hi = m.summary(rates)
    n = sum(n for _, n in per_seed)
    return f"{100 * med:.1f}% ({100 * lo:.1f}-{100 * hi:.1f}%)", f"{n:,}"


def exposure_cell(per_seed: list[int]) -> str:
    med, lo, hi = m.summary(per_seed)
    return f"{usd(med)} ({usd(lo)}-{usd(hi)})"


def money_shot_section(ms: dict) -> list[str]:
    s, f = ms["summary"], ms["featured"]
    from datetime import datetime

    gap = (datetime.fromisoformat(f["requested_at"].replace("Z", "+00:00")) - datetime.fromisoformat(f["anchor_requested_at"].replace("Z", "+00:00"))).seconds // 60
    return [
        f"## Money shot (seed {s['seed']}, single run)",
        "",
        f"Numbers shown on the page and in `docs/demo.gif`, exported to `web/public/data/seed1.json` by `make eval`. Single run of seed {s['seed']}, {CAVEAT}.",
        "",
        "| Number | Baseline | payhold |",
        "|---|---|---|",
        f"| Packets replayed | {s['packets']} | {s['packets']} |",
        f"| Bad-packet exposure paid out | {usd(s['exposure_paid_baseline_cents'])} | {usd(s['exposure_paid_payhold_cents'])} |",
        f"| Clean packets paid straight through (plain and seen look-alikes) | {s['clean_paid_baseline']} / {s['clean_packets']} | {s['clean_paid_payhold']} / {s['clean_packets']} |",
        "",
        f"Featured packet: request {f['request_id']}, the first double-factoring follower in seed {s['seed']} that the baseline paid and payhold held. "
        f"Load {f['load_no']} arrives through {f['factor']} {gap} synthetic minutes after {f['anchor_factor']} asked to pay it "
        f"(request {f['anchor_request_id']}); exposure {usd(f['exposure_cents'])}. Reason line, from the decision record: `{f['reason']}`",
        "",
    ]


def build(decisions: dict, payout: dict | None, control: dict | None, freeze: str | None, money_shot: dict | None = None) -> str:
    seeds = decisions["seeds"]
    main = {s: decisions["main"][str(s)] for s in seeds}
    heldout = {s: decisions["heldout"][str(s)] for s in seeds if str(s) in decisions.get("heldout", {})}
    n_per_seed = len(main[seeds[0]])
    runs = f"{len(seeds)} seeds x {n_per_seed}"
    agg = "aggregate: median (min-max) across seeds"
    L: list[str] = []
    L += [
        "# Numbers",
        "",
        "Every number that appears in the README, the demo or an email, and where it comes from.",
        "",
        f"All numbers are {CAVEAT}. The generator plants issues and look-alikes at rates set in "
        "`generator/settings.py`; those are planting rates, not industry rates, and nothing here implies a real "
        f"fraud rate or real savings. Seeds: {', '.join(map(str, seeds))}, {n_per_seed} packets each. "
        "Thresholds were tuned on dev seeds 101-102 only.",
    ]
    if freeze:
        L += ["", "These are the report seeds (1-5). They were never used to tune anything."]
        L += ["", f"Decision code and thresholds (`payhold/`, `config/`, `pyproject.toml`, `uv.lock`) unchanged since freeze commit `{freeze}` (`results/freeze.txt`)."]
    L += ["", "Produced by `make eval` (`eval/run.py`, `eval/report.py`); raw decisions in `results/decisions.json`.", ""]

    # ---- headline -------------------------------------------------------------------------
    L += ["## Headline", "", "| Number | What it measures | Baseline | payhold | Single run or aggregate | Runs / seeds | n | Raw output |", "|---|---|---|---|---|---|---|---|"]
    exp_b = [m.exposure_paid(main[s], "baseline") for s in seeds]
    exp_p = [m.exposure_paid(main[s], "payhold") for s in seeds]
    planted = [m.exposure_planted(main[s]) for s in seeds]
    n_bad = sum(1 for s in seeds for r in main[s] if r["issue_type"])
    L.append(
        f"| Bad-packet exposure paid out, per seed | Sum of `exposure_usd` on planted-issue packets that got \"pay\" | "
        f"{exposure_cell(exp_b)} | {exposure_cell(exp_p)} | {agg} | {runs} | {n_bad} planted-issue packets | `results/decisions.json` |"
    )
    L.append(
        f"| Planted exposure, per seed (context) | Sum of `exposure_usd` on all planted-issue packets | {exposure_cell(planted)} | same | {agg} | {runs} | {n_bad} | `results/decisions.json` |"
    )
    for label, sel, note in (
        ("plain clean", m.plain, ""),
        ("seen look-alikes", m.seen, " Designed by the same author before the freeze."),
    ):
        b, nb = rate_row([m.paid_rate(sel(main[s]), "baseline") for s in seeds])
        p, _ = rate_row([m.paid_rate(sel(main[s]), "payhold") for s in seeds])
        L.append(f"| Clean packets paid straight through: {label} | Paid / total.{note} | {b} | {p} | {agg} | {runs} | {nb} | `results/decisions.json` |")
    if heldout:
        hn = len(heldout[seeds[0]])
        h_runs = f"{len(seeds)} seeds x {hn}"
        note = (
            " Separate stream implemented after the freeze commit; decision code, thresholds and dependencies "
            "unchanged since. Each packet decided independently against the end-of-stream snapshot."
        )
        b, nb = rate_row([m.paid_rate(heldout[s], "baseline") for s in seeds])
        p, _ = rate_row([m.paid_rate(heldout[s], "payhold") for s in seeds])
        L.append(f"| Clean packets paid straight through: held-out look-alikes | Paid / total.{note} | {b} | {p} | {agg} | {h_runs} | {nb} | `results/decisions.json` |")
        for kind in sorted({r["lookalike"] for s in seeds for r in heldout[s]}):
            label = decisions.get("heldout_labels", {}).get(kind, kind)
            rows = {s: [r for r in heldout[s] if r["lookalike"] == kind] for s in seeds}
            b, nb = rate_row([m.paid_rate(rows[s], "baseline") for s in seeds])
            p, _ = rate_row([m.paid_rate(rows[s], "payhold") for s in seeds])
            L.append(f"| Held-out kind: {label} | Paid / total, this kind only | {b} | {p} | {agg} | {len(seeds)} seeds x {len(rows[seeds[0]])} | {nb} | `results/decisions.json` |")
    if payout:
        for s, what in (("a", "50 concurrent distinct requests for one load"), ("b", "50 concurrent copies of one request")):
            r = payout[s]
            val = f"{r['attempts_min']}" if r["attempts_min"] == r["attempts_max"] else f"{r['attempts_min']}-{r['attempts_max']}"
            L.append(
                f"| Duplicate payouts ({s}) | Rail attempts per load, {what}, rail dedupe off, DynamoDB Local | n/a | {val} in every trial | "
                f"aggregate: min-max across trials | {r['trials']} trials | {r['trials']} loads | `results/payout_trials.json` |"
            )
        c = payout["c"]
        att, snd = sorted(set(c["attempts_per_trial"])), sorted(set(c["sends_per_trial"]))
        L.append(
            f"| Duplicate payouts (c) | Crash after the rail call, clock past the lease, retry | n/a | {'/'.join(map(str, att))} attempts, "
            f"{'/'.join(map(str, snd))} send in every trial | aggregate across trials | {c['trials']} trials | {c['trials']} loads | `results/payout_trials.json` |"
        )
    if control:
        L.append(
            f"| Read-then-write control | Scenario (a) with the conditional write replaced by read-then-write. A race, so it varies run to run | "
            f"n/a | {control['attempts_min']}-{control['attempts_max']} rail attempts per load | single run of {control['trials']} trials, min-max | "
            f"{control['trials']} trials | {control['trials']} loads | `results/payout_naive_control.json` |"
        )
    L += ["", "Decision latency is in [`latency.md`](latency.md) (timings are kept out of this file so it stays byte-identical across runs).", ""]

    if money_shot:
        L += money_shot_section(money_shot)

    # ---- per seed -------------------------------------------------------------------------
    L += ["## Per seed", "", "| Seed | Planted exposure | Paid out: baseline | Paid out: payhold | Plain clean paid: baseline | Plain clean paid: payhold | Seen look-alikes paid: baseline | Seen look-alikes paid: payhold |", "|---|---|---|---|---|---|---|---|"]
    for s in seeds:
        r = main[s]
        pb, pn = m.paid_rate(m.plain(r), "baseline")
        pp, _ = m.paid_rate(m.plain(r), "payhold")
        sb, sn = m.paid_rate(m.seen(r), "baseline")
        sp, _ = m.paid_rate(m.seen(r), "payhold")
        L.append(
            f"| {s} | {usd(m.exposure_planted(r))} | {usd(m.exposure_paid(r, 'baseline'))} | {usd(m.exposure_paid(r, 'payhold'))} | "
            f"{pb}/{pn} | {pp}/{pn} | {sb}/{sn} | {sp}/{sn} |"
        )
    L.append("")

    # ---- detection by type ----------------------------------------------------------------
    L += [
        "## Detection by issue type",
        "",
        "Coverage check: issue types the generator plants, checks written by the same author. "
        f"Packets held, all report seeds pooled ({runs}).",
        "",
        "| # | Issue type | n | Baseline held | payhold held |",
        "|---|---|---|---|---|",
    ]
    for t, name in m.ISSUE_TYPES.items():
        hb = sum(m.held_by_type(main[s], "baseline", t)[0] for s in seeds)
        hp = sum(m.held_by_type(main[s], "payhold", t)[0] for s in seeds)
        n = sum(m.held_by_type(main[s], "baseline", t)[1] for s in seeds)
        L.append(f"| {t} | {name} | {n} | {hb} ({pct(hb, n)}) | {hp} ({pct(hp, n)}) |")
    L.append("")

    # ---- held-out detail ------------------------------------------------------------------
    if heldout:
        L += ["## Held-out look-alikes", "", "| Seed | Kind | n | Paid: baseline | Paid: payhold | payhold hold reasons |", "|---|---|---|---|---|---|"]
        for s in seeds:
            for kind in sorted({r["lookalike"] for r in heldout[s]}):
                rows = [r for r in heldout[s] if r["lookalike"] == kind]
                pb, n = m.paid_rate(rows, "baseline")
                pp, _ = m.paid_rate(rows, "payhold")
                codes: dict[str, int] = {}
                for r in rows:
                    for c in r["payhold"]["codes"]:
                        codes[c] = codes.get(c, 0) + 1
                reasons = ", ".join(f"{c} x{k}" for c, k in sorted(codes.items())) or "none"
                label = decisions.get("heldout_labels", {}).get(kind, kind)
                L.append(f"| {s} | {label} | {n} | {pb} | {pp} | {reasons} |")
        L.append("")
        dba = [r for s in seeds for r in heldout[s] if r["lookalike"] == "dba_on_bol"]
        if dba and all("bol_name_matches_ratecon" in r for r in dba):
            differ = sum(1 for r in dba if not r["bol_name_matches_ratecon"])
            L += [
                "What the DBA kind actually tests: in "
                f"{differ} of {len(dba)} DBA packets the BOL name does not match the rate con name after normalization "
                "(eval-side probe, not a decider). payhold passes them because the name check also accepts the DBA in the "
                "carrier registry. That rule was written before the freeze, but the plan already said carriers have DBAs, "
                "so this row is weaker evidence than a truly unseen look-alike would be. See `docs/design-notes.md`.",
                "",
            ]
    return "\n".join(L)


def write(results: Path, freeze: str | None, money_shot: dict | None = None) -> str:
    decisions = json.loads((results / "decisions.json").read_text())
    if (p := results / "heldout_decisions.json").exists():
        held = json.loads(p.read_text())
        decisions["heldout"], decisions["heldout_labels"] = held["heldout"], held["labels"]
    payout = json.loads(p.read_text()) if (p := results / "payout_trials.json").exists() else None
    control = json.loads(p.read_text()) if (p := results / "payout_naive_control.json").exists() else None
    text = build(decisions, payout, control, freeze, money_shot)
    (results / "numbers.md").write_text(text)
    return text
