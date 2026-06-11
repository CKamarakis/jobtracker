import { Badge } from "@/components/ui/badge";
import type { Verdict } from "@/api/types";
import { UNTRIAGED_LABEL, VERDICT_CLASS } from "@/lib/verdict";
import { cn } from "@/lib/utils";

/** Coloured pill for a triage verdict; renders a muted "untriaged" for null. */
export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  if (verdict == null) {
    return (
      <Badge variant="outline" className="text-neutral-400">
        {UNTRIAGED_LABEL}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className={cn("font-medium", VERDICT_CLASS[verdict])}>
      {verdict}
    </Badge>
  );
}
