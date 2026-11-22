import { Badge } from "@/components/ui/badge";
import { STATUS_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { TradeStatus } from "@/types/api";

const STYLE: Record<TradeStatus, string> = {
  WIN: "border-positive/40 bg-positive/10 text-positive",
  LOSS: "border-negative/40 bg-negative/10 text-negative",
  BE: "border-border bg-muted text-muted-foreground",
  OPEN: "border-primary/50 bg-primary/15 text-indigo-300",
};

/** Le libellé texte accompagne toujours la couleur (accessibilité). */
export function StatusBadge({ status, className }: { status: TradeStatus; className?: string }) {
  return (
    <Badge variant="outline" className={cn(STYLE[status], className)}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}
