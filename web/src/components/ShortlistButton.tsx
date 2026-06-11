import { Button } from "@/components/ui/button";
import { useShortlist } from "@/shortlist/ShortlistContext";

/** Toggle a job's membership in the transient shortlist. Reads/writes the Context. */
export function ShortlistButton({ id, size = "sm" }: { id: string; size?: "sm" | "default" }) {
  const { isShortlisted, toggle } = useShortlist();
  const on = isShortlisted(id);

  return (
    <Button
      type="button"
      size={size}
      variant={on ? "default" : "outline"}
      // stopPropagation: in the list, the whole row is a link to the detail page —
      // without this, clicking the button would also navigate.
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        toggle(id);
      }}
    >
      {on ? "★ Shortlisted" : "☆ Shortlist"}
    </Button>
  );
}
