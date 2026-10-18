"use client";

import { usd, type Step } from "./types";

const W = 1040;
const H = 300;
const PAD = { l: 72, r: 16, t: 14, b: 40 };

export default function Chart({
  stream,
  shown,
  featuredId,
  onPick,
}: {
  stream: Step[];
  shown: number;
  featuredId: string;
  onPick: (s: Step) => void;
}) {
  const n = stream.length;
  const final = stream[n - 1].cum_baseline_cents;
  const step = niceStep(final / 4);
  const yMax = Math.ceil(final / step) * step || 1;
  const x = (i: number) => PAD.l + (i / n) * (W - PAD.l - PAD.r);
  const y = (c: number) => H - PAD.b - (c / yMax) * (H - PAD.t - PAD.b);

  const line = (key: "cum_baseline_cents" | "cum_payhold_cents") => {
    const pts = [`${x(0)},${y(0)}`];
    for (let i = 0; i < shown; i++) {
      const prev = i === 0 ? 0 : stream[i - 1][key];
      pts.push(`${x(i)},${y(prev)}`, `${x(i + 1)},${y(stream[i][key])}`);
    }
    return pts.join(" ");
  };

  // Packets payhold held and the baseline paid: the ones the cross-factor and registry checks add.
  const caught = stream.slice(0, shown).filter((s) => s.payhold === "hold" && s.baseline === "pay");
  const ticks = Array.from({ length: Math.round(yMax / step) + 1 }, (_, i) => i * step);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label="Cumulative exposure paid out">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="#e2e8f0" />
          <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#64748b">
            {usd(t)}
          </text>
        </g>
      ))}
      {[0, 100, 200, 300, 400, 500].filter((v) => v <= n).map((v) => (
        <text key={v} x={x(v)} y={H - PAD.b + 16} textAnchor="middle" fontSize="11" fill="#64748b">
          {v}
        </text>
      ))}
      <text x={(W + PAD.l) / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="#64748b">
        packets, in arrival order
      </text>

      <polyline points={line("cum_baseline_cents")} fill="none" stroke="#dc2626" strokeWidth="2.5" />
      <polyline points={line("cum_payhold_cents")} fill="none" stroke="#2563eb" strokeWidth="2.5" />

      {caught.map((s) => {
        const feat = s.request_id === featuredId;
        return (
          <circle
            key={s.request_id}
            cx={x(s.seq + 1)}
            cy={y(s.cum_payhold_cents)}
            r={feat ? 7 : 3.5}
            fill={feat ? "#2563eb" : "#93c5fd"}
            stroke={feat ? "#1e3a8a" : "none"}
            strokeWidth={2}
            className="cursor-pointer"
            onClick={() => onPick(s)}
          >
            <title>{`${s.request_id}: held (${s.issue_name.replace("_", " ")})`}</title>
          </circle>
        );
      })}

      <g transform={`translate(${PAD.l + 12}, ${PAD.t + 8})`}>
        <rect width="250" height="44" fill="white" stroke="#e2e8f0" rx="4" />
        <line x1="10" x2="30" y1="15" y2="15" stroke="#dc2626" strokeWidth="2.5" />
        <text x="38" y="19" fontSize="12">Baseline (one factor's own book)</text>
        <line x1="10" x2="30" y1="32" y2="32" stroke="#2563eb" strokeWidth="2.5" />
        <text x="38" y="36" fontSize="12">payhold (dots: held, baseline paid)</text>
      </g>
    </svg>
  );
}

function niceStep(raw: number) {
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= raw) return m * p;
  return 10 * p;
}
