import { Card, CardContent } from "@/components/ui/card";
import { TONE_CLASS, type Tone } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Tuile de statistique. `value === null` = statistique non définie : on l'écrit en toutes lettres
 * avec sa raison, jamais « 0 » ni « ∞ ».
 */
export function StatTile({
  label,
  value,
  tone = "neutral",
  undefinedReason,
  hint,
  className,
}: {
  label: string;
  value: string | null;
  tone?: Tone;
  /** Pourquoi la valeur n'est pas définie (affiché à la place de la valeur). */
  undefinedReason?: string;
  hint?: string;
  className?: string;
}) {
  const undefinedValue = value === null;
  return (
    <Card className={className}>
      <CardContent className="space-y-1 pt-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        {undefinedValue ? (
          <>
            <p className="text-lg font-medium text-muted-foreground">Non défini</p>
            {undefinedReason && <p className="text-xs text-muted-foreground">{undefinedReason}</p>}
          </>
        ) : (
          <>
            <p className={cn("tabular text-2xl font-semibold", tone !== "neutral" ? TONE_CLASS[tone] : "")}>{value}</p>
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}
