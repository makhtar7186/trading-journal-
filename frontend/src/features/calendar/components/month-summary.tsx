import { formatR, toneOf } from "@/lib/format";
import type { CalendarMonth } from "@/types/api";
import { StatTile } from "@/features/analytics/components/stat-tile";

/** Totaux du mois, déduits des jours affichés (jamais contradictoires avec la grille). */
export function MonthSummary({ summary }: { summary: CalendarMonth["summary"] }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatTile
        label="Résultat du mois"
        value={summary.total_r === null ? null : formatR(summary.total_r, { signed: true })}
        tone={toneOf(summary.total_r)}
        undefinedReason="Aucun trade clôturé ce mois-ci."
      />
      <StatTile
        label="Trades clôturés"
        value={String(summary.closed_trades)}
        hint={`${summary.wins} G · ${summary.losses} P · ${summary.break_even} BE`}
      />
      <StatTile
        label="Jours avec trades"
        value={String(summary.days_with_trades)}
        hint={summary.open_trades > 0 ? `dont ${summary.open_trades} trade${summary.open_trades > 1 ? "s" : ""} ouvert${summary.open_trades > 1 ? "s" : ""}` : undefined}
      />
    </div>
  );
}
