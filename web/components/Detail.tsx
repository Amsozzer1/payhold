"use client";

import { usd, when, type Featured, type Step } from "./types";

const DOCS = [
  ["ratecon", "Rate confirmation"],
  ["bol", "BOL / proof of delivery"],
  ["invoice", "Carrier invoice"],
] as const;

export default function Detail({ step, featured, onClose }: { step: Step; featured: Featured | null; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-10 flex items-start justify-center bg-slate-900/50 p-4" onClick={onClose}>
      <div
        id="detail"
        className="w-full max-w-6xl rounded-lg bg-white p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">
              Request {step.request_id} through {step.factor}, {when(step.requested_at)} (synthetic clock)
            </div>
            <div className="mt-1 flex gap-3 text-sm">
              <span className="rounded bg-red-50 px-2 py-0.5 text-red-700">Baseline: {step.baseline}</span>
              <span className="rounded bg-blue-50 px-2 py-0.5 text-blue-700">payhold: {step.payhold}</span>
              {step.exposure_cents > 0 && <span className="text-slate-600">exposure {usd(step.exposure_cents)}</span>}
            </div>
          </div>
          <button onClick={onClose} className="text-sm text-slate-500 hover:text-slate-800">
            Close
          </button>
        </div>

        {step.reasons.map((r) => (
          <p key={r} className="mt-3 rounded border border-blue-200 bg-blue-50 px-3 py-2 font-mono text-[13px] text-blue-900">
            {r}
          </p>
        ))}
        {featured && (
          <p className="mt-1 text-xs text-slate-500">
            Boxes mark the load number and BOL number on each document. The first request ({featured.anchor_request_id}) came
            through {featured.anchor_factor} at {when(featured.anchor_requested_at)}; the baseline only sees{" "}
            {featured.factor}&apos;s own book, so it paid this one.
          </p>
        )}

        {step.pages && (
          <div className="mt-3 grid grid-cols-3 gap-3">
            {DOCS.map(([doc, label]) => (
              <figure key={doc} className="overflow-hidden rounded border border-slate-200">
                {/* Cropped to the field area of the 850 x 1100 px page so the boxes are readable. */}
                <div className="relative overflow-hidden" style={{ aspectRatio: "560 / 380" }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/data/pages/${step.request_id}/${doc}.png`}
                    alt={`${label}, request ${step.request_id} (synthetic)`}
                    className="absolute max-w-none"
                    style={{ width: `${(850 / 560) * 100}%`, left: `${(-55 / 560) * 100}%`, top: `${(-90 / 380) * 100}%` }}
                  />
                </div>
                <figcaption className="border-t border-slate-200 px-2 py-1 text-xs text-slate-600">{label}</figcaption>
              </figure>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
