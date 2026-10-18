export type Step = {
  seq: number;
  request_id: string;
  factor: string;
  requested_at: string;
  issue_type: number;
  issue_name: string;
  lookalike: string | null;
  exposure_cents: number;
  baseline: "pay" | "hold";
  payhold: "pay" | "hold";
  reasons: string[];
  cum_baseline_cents: number;
  cum_payhold_cents: number;
  pages: boolean;
};

export type Featured = {
  request_id: string;
  seq: number;
  factor: string;
  requested_at: string;
  anchor_request_id: string;
  anchor_factor: string;
  anchor_requested_at: string;
  exposure_cents: number;
  load_no: string;
  bol_no: string;
  reason: string;
  baseline: string;
  payhold: string;
};

export type Summary = {
  seed: number;
  packets: number;
  clean_packets: number;
  clean_paid_baseline: number;
  clean_paid_payhold: number;
  bad_packets: number;
  exposure_planted_cents: number;
  exposure_paid_baseline_cents: number;
  exposure_paid_payhold_cents: number;
};

export type Seed = { synthetic: boolean; summary: Summary; featured: Featured; stream: Step[] };

export const usd = (cents: number) => `$${Math.round(cents / 100).toLocaleString("en-US")}`;

export const when = (iso: string) => {
  const d = new Date(iso);
  const mon = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${mon} ${d.getUTCDate()}, ${hh}:${mm}`;
};
