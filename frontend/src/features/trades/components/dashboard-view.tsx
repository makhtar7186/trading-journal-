"use client";

import Link from "next/link";
import { Plus } from "lucide-react";

import { PageHeader } from "@/components/shared/page-header";
import { RValue } from "@/components/shared/r-value";
import { StatusBadge } from "@/components/shared/status-badge";
import { EmptyState, ErrorState, LoadingRows } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DistributionBar } from "@/features/analytics/components/distribution-bar";
import { EquityChart } from "@/features/analytics/components/equity-chart";
import { FiltersBar } from "@/features/analytics/components/filters-bar";
import { OverviewKpis } from "@/features/analytics/components/overview-kpis";
import { useEquityCurve, useOverview } from "@/features/analytics/hooks";
import { useFilterState } from "@/features/analytics/use-filter-state";
import { useAuth, useTimeZone } from "@/features/auth/auth-provider";
import { formatDateTime } from "@/lib/datetime";
import { useTrades } from "../hooks";

/**
 * Dashboard : tous les chiffres viennent du backend (source de vérité), calculés sur les trades
 * CLÔTURÉS uniquement et filtrés avant agrégation. « Derniers trades » est volontairement hors filtres.
 */
export function DashboardView() {
  const { user } = useAuth();
  const tz = useTimeZone();
  const filters = useFilterState();
  const overview = useOverview(filters.params);
  const equity = useEquityCurve(filters.params);
  const recent = useTrades({ page_size: 5, ordering: "-trade_date" });

  const noClosedTrades = overview.data?.closed_trades === 0;

  return (
    <>
      <PageHeader title="Dashboard" description={user ? `Bonjour ${user.username}.` : undefined} />

      <FiltersBar state={filters.state} onChange={filters.update} onReset={filters.reset} active={filters.active} />

      {overview.isError ? (
        <ErrorState message="Impossible de charger les statistiques." onRetry={() => void overview.refetch()} />
      ) : overview.isPending ? (
        <LoadingRows rows={3} />
      ) : (
        <div aria-busy={overview.isFetching} className="space-y-4">
          <OverviewKpis overview={overview.data} />

          {noClosedTrades ? (
            <EmptyState
              title={filters.active ? "Aucun trade clôturé pour ces filtres" : "Aucun trade clôturé pour l'instant"}
              description={
                filters.active
                  ? "Élargissez la période ou réinitialisez les filtres. Les trades ouverts ne comptent pas dans les statistiques."
                  : "Les statistiques se calculent à partir des trades clôturés : clôturez un trade en saisissant son RR réalisé."
              }
              action={
                filters.active ? (
                  <Button variant="outline" onClick={filters.reset}>
                    Réinitialiser les filtres
                  </Button>
                ) : (
                  <Button asChild>
                    <Link href="/trades/new">
                      <Plus aria-hidden /> Ajouter un trade
                    </Link>
                  </Button>
                )
              }
            />
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Répartition par résultat</CardTitle>
                  <CardDescription>Trades clôturés uniquement (les trades ouverts sont exclus).</CardDescription>
                </CardHeader>
                <CardContent>
                  <DistributionBar wins={overview.data.wins} losses={overview.data.losses} breakEven={overview.data.break_even} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Courbe de performance</CardTitle>
                  <CardDescription>Cumul des RR réalisés, trade par trade, dans l&apos;ordre de clôture.</CardDescription>
                </CardHeader>
                <CardContent>
                  {equity.isError ? (
                    <ErrorState message="Impossible de charger la courbe." onRetry={() => void equity.refetch()} />
                  ) : equity.isPending ? (
                    <LoadingRows rows={3} />
                  ) : (
                    <EquityChart points={equity.data.points} totalR={equity.data.total_r} />
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Derniers trades</CardTitle>
        </CardHeader>
        <CardContent>
          {recent.isError ? (
            <ErrorState message="Impossible de charger les trades." onRetry={() => void recent.refetch()} />
          ) : recent.isPending ? (
            <LoadingRows rows={3} />
          ) : recent.data.results.length === 0 ? (
            <EmptyState
              title="Aucun trade pour l'instant"
              description="Ajoutez votre premier trade pour alimenter le journal."
              action={
                <Button asChild>
                  <Link href="/trades/new">
                    <Plus aria-hidden /> Ajouter un trade
                  </Link>
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-border">
              {recent.data.results.map((trade) => (
                <li key={trade.id}>
                  <Link
                    href={`/trades/${trade.id}`}
                    className="flex items-center justify-between gap-3 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{trade.name}</p>
                      <p className="text-xs text-muted-foreground">
                        <span className="font-mono">{trade.asset}</span> · {formatDateTime(trade.trade_date, tz)}
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
          )}
        </CardContent>
      </Card>
    </>
  );
}
