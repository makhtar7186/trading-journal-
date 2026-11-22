"use client";

import Link from "next/link";

import { RValue } from "@/components/shared/r-value";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useTimeZone } from "@/features/auth/auth-provider";
import { dayLabel } from "@/lib/calendar";
import { formatTime } from "@/lib/datetime";
import { DIRECTION_LABEL } from "@/lib/labels";
import type { CalendarDay } from "@/types/api";

/** Trades du jour sélectionné. Un trade ouvert est rattaché au jour de sa prise, sans résultat. */
export function DayPanel({ date, day }: { date: string | null; day: CalendarDay | undefined }) {
  const tz = useTimeZone();

  return (
    <Card aria-live="polite">
      <CardHeader>
        <CardTitle className="first-letter:uppercase">{date ? dayLabel(date) : "Détail du jour"}</CardTitle>
        <CardDescription>
          {!date
            ? "Sélectionnez un jour dans le calendrier pour voir ses trades."
            : !day
              ? "Aucun trade ce jour-là."
              : day.total_r === null
                ? "Aucun trade clôturé ce jour-là (résultat non défini)."
                : `${day.closed_trades} trade${day.closed_trades > 1 ? "s" : ""} clôturé${day.closed_trades > 1 ? "s" : ""} : ${day.wins} gagnant${day.wins > 1 ? "s" : ""}, ${day.losses} perdant${day.losses > 1 ? "s" : ""}, ${day.break_even} break-even.`}
        </CardDescription>
      </CardHeader>
      {day && (
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <div>
              <p className="text-xs text-muted-foreground">Résultat du jour</p>
              {day.total_r === null ? (
                <p className="text-lg font-medium text-muted-foreground">Non défini</p>
              ) : (
                <RValue value={day.total_r} className="text-2xl font-semibold" />
              )}
            </div>
            {day.open_trades > 0 && (
              <p className="text-sm text-muted-foreground">
                {day.open_trades} trade{day.open_trades > 1 ? "s" : ""} ouvert{day.open_trades > 1 ? "s" : ""} pris ce jour-là
              </p>
            )}
          </div>

          <ul className="divide-y divide-border">
            {day.trades.map((trade) => (
              <li key={trade.id}>
                <Link
                  href={`/trades/${trade.id}`}
                  className="flex items-center justify-between gap-3 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{trade.name}</p>
                    <p className="text-xs text-muted-foreground">
                      <span className="font-mono">{trade.asset}</span> · {DIRECTION_LABEL[trade.direction]} ·{" "}
                      {trade.status === "OPEN" ? "pris" : "clôturé"} à {formatTime(trade.at, tz)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <RValue value={trade.realized_rr} className="text-sm font-medium" />
                    <StatusBadge status={trade.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  );
}
