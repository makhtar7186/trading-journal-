"use client";

import { ChevronLeft, ChevronRight, X } from "lucide-react";

import { FilterSelect } from "@/components/shared/filter-select";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState, LoadingRows } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useStrategies } from "@/features/strategies/hooks";
import { currentMonth, monthLabel, shiftMonth } from "@/lib/calendar";
import { MARKET_OPTIONS } from "@/lib/labels";
import { useTimeZone } from "@/features/auth/auth-provider";
import { useCalendar } from "../hooks";
import { useCalendarState } from "../use-calendar-state";
import { CalendarGrid } from "./calendar-grid";
import { DayPanel } from "./day-panel";
import { MonthSummary } from "./month-summary";

export function CalendarView() {
  const tz = useTimeZone();
  const { state, today, update, filtersActive } = useCalendarState();
  const strategies = useStrategies();
  const query = useCalendar({
    month: state.month,
    ...(state.market_type ? { market_type: state.market_type } : {}),
    ...(state.strategy ? { strategy: state.strategy } : {}),
  });

  const strategyOptions: [string, string][] = [
    ["none", "Sans stratégie"],
    ...(strategies.data?.results ?? []).map((s): [string, string] => [s.id, s.name]),
  ];
  const days = query.data?.days ?? [];
  const selected = state.day ? days.find((d) => d.date === state.day) : undefined;
  const isCurrentMonth = state.month === currentMonth(tz);

  return (
    <>
      <PageHeader
        title="Calendrier"
        description="Résultat quotidien en R. Un trade clôturé apparaît le jour de sa clôture, un trade ouvert le jour où il a été pris."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon" aria-label="Mois précédent" onClick={() => update({ month: shiftMonth(state.month, -1), day: null })}>
          <ChevronLeft />
        </Button>
        <h2 aria-live="polite" className="min-w-40 text-center text-lg font-semibold capitalize">
          {monthLabel(state.month)}
        </h2>
        <Button variant="outline" size="icon" aria-label="Mois suivant" onClick={() => update({ month: shiftMonth(state.month, 1), day: null })}>
          <ChevronRight />
        </Button>
        <Button variant="outline" disabled={isCurrentMonth} onClick={() => update({ month: currentMonth(tz), day: today })}>
          Aujourd&apos;hui
        </Button>
      </div>

      <div className="mb-4 grid gap-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-3">
        <FilterSelect id="c-market" label="Marché" value={state.market_type} onChange={(v) => update({ market_type: v })} options={MARKET_OPTIONS} allLabel="Tous les marchés" />
        <FilterSelect id="c-strategy" label="Stratégie" value={state.strategy} onChange={(v) => update({ strategy: v })} options={strategyOptions} allLabel="Toutes les stratégies" />
        <div className="flex items-end">
          <Button variant="ghost" disabled={!filtersActive} onClick={() => update({ market_type: "", strategy: "" })}>
            <X aria-hidden /> Réinitialiser
          </Button>
        </div>
      </div>

      {query.isError ? (
        <ErrorState message="Impossible de charger le calendrier." onRetry={() => void query.refetch()} />
      ) : query.isPending ? (
        <LoadingRows rows={6} />
      ) : (
        <div aria-busy={query.isFetching} className="space-y-4">
          <MonthSummary summary={query.data.summary} />
          {query.data.summary.days_with_trades === 0 && (
            <p className="rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
              {filtersActive ? "Aucun trade ce mois-ci pour ces filtres." : "Aucun trade ce mois-ci."}
            </p>
          )}
          <Card>
            <CardContent className="pt-4">
              <CalendarGrid
                month={state.month}
                days={days}
                selectedDay={state.day}
                today={today}
                onSelectDay={(day) => update({ day })}
                onMonthChange={(month) => update({ month, day: null })}
              />
            </CardContent>
          </Card>
          <DayPanel date={state.day} day={selected} />
        </div>
      )}
    </>
  );
}
