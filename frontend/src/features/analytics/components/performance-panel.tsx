"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTimeZone } from "@/features/auth/auth-provider";
import { formatDate } from "@/lib/datetime";
import { formatR, toneOf } from "@/lib/format";
import type { Performance, TradeRef } from "@/types/api";
import { StatTile } from "./stat-tile";

function TradeTile({ label, trade, emptyReason }: { label: string; trade: TradeRef | null; emptyReason: string }) {
  const tz = useTimeZone();
  return (
    <Card>
      <CardContent className="space-y-1 pt-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        {trade === null ? (
          <>
            <p className="text-lg font-medium text-muted-foreground">Non défini</p>
            <p className="text-xs text-muted-foreground">{emptyReason}</p>
          </>
        ) : (
          <>
            <p className={`tabular text-2xl font-semibold ${toneOf(trade.realized_rr) === "positive" ? "text-positive" : "text-negative"}`}>
              {formatR(trade.realized_rr, { signed: true })}
            </p>
            <Link href={`/trades/${trade.trade_id}`} className="block truncate text-sm hover:underline">
              {trade.name}
            </Link>
            <p className="text-xs text-muted-foreground">
              {trade.asset} · {formatDate(trade.closed_at, tz)}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Détail de la performance : gain/perte moyens, extrêmes, séries. Les BE sont ignorés dans les séries. */
export function PerformancePanel({ performance }: { performance: Performance }) {
  const { streaks } = performance;
  const current =
    streaks.current_type === null
      ? null
      : `${streaks.current_length} ${streaks.current_type === "WIN" ? "gain" : "perte"}${streaks.current_length > 1 ? "s" : ""}`;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Gain moyen"
          value={performance.average_win_r === null ? null : formatR(performance.average_win_r, { signed: true })}
          tone="positive"
          undefinedReason="Aucun trade gagnant."
          hint="Moyenne des RR positifs"
        />
        <StatTile
          label="Perte moyenne"
          value={performance.average_loss_r === null ? null : formatR(performance.average_loss_r)}
          tone="negative"
          undefinedReason="Aucun trade perdant."
          hint="Valeur signée (négative)"
        />
        <TradeTile label="Meilleur trade" trade={performance.best_trade} emptyReason="Aucun trade gagnant." />
        <TradeTile label="Pire trade" trade={performance.worst_trade} emptyReason="Aucun trade perdant." />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Gains cumulés"
          value={performance.gross_profit_r === null ? null : formatR(performance.gross_profit_r, { signed: true })}
          tone="positive"
          undefinedReason="Aucun trade gagnant."
        />
        <StatTile
          label="Pertes cumulées"
          value={performance.gross_loss_r === null ? null : formatR(performance.gross_loss_r)}
          tone="negative"
          undefinedReason="Aucun trade perdant."
        />
        <Card className="col-span-2">
          <CardHeader className="pb-0">
            <CardTitle className="text-sm font-normal text-muted-foreground">Séries (break-even ignorés)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-x-8 gap-y-2 pt-2">
            <div>
              <p className="tabular text-2xl font-semibold text-positive">{streaks.max_win}</p>
              <p className="text-xs text-muted-foreground">gains d&apos;affilée (max)</p>
            </div>
            <div>
              <p className="tabular text-2xl font-semibold text-negative">{streaks.max_loss}</p>
              <p className="text-xs text-muted-foreground">pertes d&apos;affilée (max)</p>
            </div>
            <div>
              <p className="text-2xl font-semibold">{current ?? "—"}</p>
              <p className="text-xs text-muted-foreground">série en cours</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
