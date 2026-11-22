"use client";

import { formatPercent, formatR, formatRatio, toneOf } from "@/lib/format";
import type { Overview } from "@/types/api";
import { StatTile } from "./stat-tile";

/** Indicateurs clés du dashboard. Valeurs telles que calculées par le serveur (aucun recalcul ici). */
export function OverviewKpis({ overview }: { overview: Overview }) {
  const none = overview.closed_trades === 0;
  const noTrades = "Aucun trade clôturé.";
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <StatTile
        label="Performance cumulée"
        value={overview.total_r === null ? null : formatR(overview.total_r, { signed: true })}
        tone={toneOf(overview.total_r)}
        undefinedReason={noTrades}
        hint="Somme des RR réalisés"
      />
      <StatTile
        label="Win rate"
        value={overview.win_rate === null ? null : formatPercent(overview.win_rate)}
        undefinedReason={none ? noTrades : "Aucun trade gagnant ni perdant."}
        hint="Break-even exclus"
      />
      <StatTile
        label="Expectancy"
        value={overview.expectancy_r === null ? null : formatR(overview.expectancy_r, { signed: true })}
        tone={toneOf(overview.expectancy_r)}
        undefinedReason={noTrades}
        hint="RR moyen réalisé par trade"
      />
      <StatTile
        label="Profit factor"
        value={overview.profit_factor === null ? null : formatRatio(overview.profit_factor)}
        undefinedReason={none ? noTrades : "Aucune perte : ratio non défini."}
        hint="Gains / pertes (en R)"
      />
      <StatTile
        label="Trades clôturés"
        value={String(overview.closed_trades)}
        hint={`${overview.open_trades} ouvert${overview.open_trades > 1 ? "s" : ""} (exclus des statistiques)`}
        className="col-span-2 md:col-span-1"
      />
    </div>
  );
}
