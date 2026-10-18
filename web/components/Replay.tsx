"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Chart from "./Chart";
import Detail from "./Detail";
import { usd, type Seed, type Step } from "./types";

export type { Seed } from "./types";

const REPLAY_MS = 10_000;

export default function Replay({ data }: { data: Seed }) {
  const { stream, featured, summary } = data;
  const [shown, setShown] = useState(0);
  const [open, setOpen] = useState<Step | null>(null);
  const raf = useRef<number | null>(null);

  const play = () => {
    if (raf.current) cancelAnimationFrame(raf.current);
    setOpen(null);
    const start = performance.now();
    const tick = (now: number) => {
      const k = Math.min(stream.length, Math.ceil(((now - start) / REPLAY_MS) * stream.length));
      setShown(k);
      if (k < stream.length) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };

  useEffect(() => {
    play();
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = useMemo(() => {
    const seen = stream.slice(0, shown);
    const clean = seen.filter((s) => !s.issue_type);
    const last = seen[seen.length - 1];
    return {
      clean: clean.length,
      cleanPaidBaseline: clean.filter((s) => s.baseline === "pay").length,
      cleanPaidPayhold: clean.filter((s) => s.payhold === "pay").length,
      exposureBaseline: last ? last.cum_baseline_cents : 0,
      exposurePayhold: last ? last.cum_payhold_cents : 0,
    };
  }, [stream, shown]);

  const featuredStep = stream.find((s) => s.request_id === featured.request_id)!;
  const done = shown >= stream.length;

  return (
    <main className="mx-auto max-w-6xl px-6 py-6">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">payhold</h1>
          <p className="text-sm text-slate-600">
            A paperwork-to-payout check for factored freight invoices, run on synthetic data.
          </p>
        </div>
        <span className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
          SYNTHETIC DATA
        </span>
      </header>

      <section className="mt-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold">
            Seed {summary.seed}: {summary.packets} packets replayed in arrival order
          </h2>
          <button
            onClick={play}
            className="rounded border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50"
          >
            Replay
          </button>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Cumulative bad-packet exposure paid out. Synthetic packets with planted issues at configured rates, not
          industry rates.
        </p>

        <Chart stream={stream} shown={shown} featuredId={featured.request_id} onPick={setOpen} />

        <div className="mt-3 grid grid-cols-[0.6fr_1fr_1fr] gap-3 text-sm">
          <Counter label="Packets replayed" value={`${shown} / ${stream.length}`} />
          <Counter
            label="Bad-packet exposure paid out"
            baseline={usd(counts.exposureBaseline)}
            payhold={usd(counts.exposurePayhold)}
          />
          <Counter
            label="Clean packets paid straight through"
            baseline={`${counts.cleanPaidBaseline} / ${counts.clean}`}
            payhold={`${counts.cleanPaidPayhold} / ${counts.clean}`}
          />
        </div>

        <div className="mt-4 flex items-center justify-between rounded border border-blue-100 bg-blue-50 px-4 py-2 text-sm">
          <span>
            Request {featured.request_id}: load {featured.load_no} arrives through {featured.factor},{" "}
            {minutesBetween(featured.anchor_requested_at, featured.requested_at)} synthetic minutes after{" "}
            {featured.anchor_factor} asked to pay the same load.
          </span>
          <button
            id="open-featured"
            onClick={() => setOpen(featuredStep)}
            disabled={!done && shown <= featuredStep.seq}
            className="ml-4 shrink-0 rounded bg-blue-600 px-3 py-1 font-medium text-white hover:bg-blue-700 disabled:opacity-40"
          >
            Show the held packet
          </button>
        </div>
      </section>

      {open && <Detail step={open} featured={open.request_id === featured.request_id ? featured : null} onClose={() => setOpen(null)} />}
    </main>
  );
}

function minutesBetween(a: string, b: string) {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000);
}

function Counter({ label, value, baseline, payhold }: { label: string; value?: string; baseline?: string; payhold?: string }) {
  return (
    <div className="rounded border border-slate-200 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      {value !== undefined ? (
        <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
      ) : (
        <div className="mt-1 flex gap-5 whitespace-nowrap tabular-nums">
          <span>
            <span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-600" />
            Baseline <b className="text-lg">{baseline}</b>
          </span>
          <span>
            <span className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-600" />
            payhold <b className="text-lg">{payhold}</b>
          </span>
        </div>
      )}
    </div>
  );
}
