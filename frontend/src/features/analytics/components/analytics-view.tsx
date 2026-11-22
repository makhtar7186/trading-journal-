"use client";

import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState, LoadingRows } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Granularity } from "@/types/api";
import { useGroups, useOverview, usePerformance, usePeriods } from "../hooks";
import { useFilterState } from "../use-filter-state";
import { FiltersBar } from "./filters-bar";
import { GroupsTable } from "./groups-table";
import { OverviewKpis } from "./overview-kpis";
import { PeriodChart } from "./period-chart";
import { PerformancePanel } from "./performance-panel";

export function AnalyticsView() {
  const filters = useFilterState();
  const [granularity, setGranularity] = useState<Granularity>("month");
  const overview = useOverview(filters.params);
  const performance = usePerformance(filters.params);
  const periods = usePeriods(granularity, filters.params);
  const byAsset = useGroups("asset", filters.params);
  const byMarket = useGroups("market", filters.params);
  const byStrategy = useGroups("strategy", filters.params);

  const noClosedTrades = overview.data?.closed_trades === 0;

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Calculées par le serveur sur vos trades clôturés, en R. Les trades ouverts sont exclus."
      />
      <FiltersBar state={filters.state} onChange={filters.update} onReset={filters.reset} active={filters.active} />

      {overview.isError ? (
        <ErrorState message="Impossible de charger les statistiques." onRetry={() => void overview.refetch()} />
      ) : overview.isPending ? (
        <LoadingRows rows={4} />
      ) : noClosedTrades ? (
        <EmptyState
          title={filters.active ? "Aucun trade clôturé pour ces filtres" : "Aucun trade clôturé pour l'instant"}
          description="Les analyses apparaissent dès qu'un trade est clôturé avec son RR réalisé."
          action={
            filters.active ? (
              <Button variant="outline" onClick={filters.reset}>
                Réinitialiser les filtres
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div aria-busy={overview.isFetching} className="space-y-6">
          <OverviewKpis overview={overview.data} />

          <section aria-labelledby="perf-title" className="space-y-3">
            <h2 id="perf-title" className="text-lg font-semibold">
              Performance
            </h2>
            {performance.isError ? (
              <ErrorState message="Impossible de charger le détail." onRetry={() => void performance.refetch()} />
            ) : performance.isPending ? (
              <LoadingRows rows={2} />
            ) : (
              <PerformancePanel performance={performance.data} />
            )}
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Résultat par période</CardTitle>
              <CardDescription>En R, selon la date de clôture (jours calculés dans votre fuseau horaire).</CardDescription>
            </CardHeader>
            <CardContent>
              {periods.isError ? (
                <ErrorState message="Impossible de charger les périodes." onRetry={() => void periods.refetch()} />
              ) : periods.isPending ? (
                <LoadingRows rows={3} />
              ) : (
                <PeriodChart periods={periods.data.periods} granularity={granularity} onGranularityChange={setGranularity} />
              )}
            </CardContent>
          </Card>

          <GroupsTable title="Résultats par actif" firstColumn="Actif" groups={byAsset.data?.groups} loading={byAsset.isPending} />
          <GroupsTable title="Résultats par marché" firstColumn="Marché" groups={byMarket.data?.groups} loading={byMarket.isPending} />
          <GroupsTable title="Résultats par stratégie" firstColumn="Stratégie" groups={byStrategy.data?.groups} loading={byStrategy.isPending} />
        </div>
      )}
    </>
  );
}
