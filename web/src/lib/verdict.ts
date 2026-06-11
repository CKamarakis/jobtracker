import type { Verdict } from "@/api/types";

// Presentation metadata for each verdict. The *ordering* is the API's job (it sorts
// strongest-first); this is only how a verdict looks in the UI. Tailwind colour
// utilities live here so a verdict's colour is defined once.

export const VERDICTS: Verdict[] = ["strong fit", "fit", "stretch", "reject"];

/** Tailwind classes for a verdict badge. Tuned for the light/neutral shadcn theme. */
export const VERDICT_CLASS: Record<Verdict, string> = {
  "strong fit": "bg-emerald-100 text-emerald-800 border-emerald-200",
  fit: "bg-sky-100 text-sky-800 border-sky-200",
  stretch: "bg-amber-100 text-amber-800 border-amber-200",
  reject: "bg-neutral-100 text-neutral-500 border-neutral-200",
};

/** Label for an untriaged job (triage_verdict === null). */
export const UNTRIAGED_LABEL = "untriaged";
