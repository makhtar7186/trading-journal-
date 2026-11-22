import { formatR, TONE_CLASS, toneOf } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Valeur en R : signe explicite + couleur + chiffres tabulaires. « — » si absente. */
export function RValue({
  value,
  className,
  colored = true,
}: {
  value: string | null | undefined;
  className?: string;
  colored?: boolean;
}) {
  return (
    <span className={cn("tabular", colored && TONE_CLASS[toneOf(value)], className)}>
      {formatR(value, { signed: true })}
    </span>
  );
}
