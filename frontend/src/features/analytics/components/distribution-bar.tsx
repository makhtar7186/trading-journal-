import { CheckCircle2, MinusCircle, XCircle } from "lucide-react";

import { CHART } from "../chart-theme";

interface Part {
  key: "WIN" | "LOSS" | "BE";
  label: string;
  count: number;
  color: string;
  icon: typeof CheckCircle2;
}

/**
 * Répartition des trades clôturés : barre segmentée (≤ 3 parties).
 * Chaque état a une couleur, une icône et un libellé (jamais la couleur seule) ; la valeur
 * est imprimée dans le segment quand il est assez large, sinon dans la légende.
 */
export function DistributionBar({ wins, losses, breakEven }: { wins: number; losses: number; breakEven: number }) {
  const parts: Part[] = [
    { key: "WIN", label: "Gagnants", count: wins, color: CHART.positive, icon: CheckCircle2 },
    { key: "LOSS", label: "Perdants", count: losses, color: CHART.negative, icon: XCircle },
    { key: "BE", label: "Break-even", count: breakEven, color: CHART.neutral, icon: MinusCircle },
  ];
  const total = wins + losses + breakEven;
  const summary = parts.map((p) => `${p.count} ${p.label.toLowerCase()}`).join(", ");

  return (
    <div>
      <div
        role="img"
        aria-label={`Répartition des ${total} trades clôturés : ${summary}`}
        className="flex h-7 w-full gap-0.5 overflow-hidden rounded-md"
        style={{ backgroundColor: CHART.surface }}
      >
        {parts
          .filter((p) => p.count > 0)
          .map((p) => {
            const share = (p.count / total) * 100;
            return (
              <div
                key={p.key}
                title={`${p.label} : ${p.count} (${share.toFixed(0)} %)`}
                className="flex min-w-0 items-center rounded-[4px] px-2 text-xs font-semibold"
                style={{ width: `${share}%`, backgroundColor: p.color, color: CHART.onFill }}
              >
                {/* Imprimé seulement si le segment est assez large : jamais de texte rogné. */}
                {share >= 12 && <span className="tabular">{p.count}</span>}
              </div>
            );
          })}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-1.5">
            <p.icon className="size-4" style={{ color: p.color }} aria-hidden />
            <span className="text-muted-foreground">{p.label}</span>
            <span className="tabular font-medium">{p.count}</span>
            {total > 0 && <span className="tabular text-xs text-muted-foreground">({Math.round((p.count / total) * 100)} %)</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
