"use client";

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { RValue } from "@/components/shared/r-value";
import { Button } from "@/components/ui/button";
import { formatPercent } from "@/lib/format";
import type { Granularity, Period } from "@/types/api";
import { AXIS_TICK, CHART } from "../chart-theme";

export const GRANULARITY_LABEL: Record<Granularity, string> = { day: "Jour", week: "Semaine", month: "Mois" };

/** "2026-11" → "nov. 2026" ; "2026-11-09" → "9 nov." (lundi pour une semaine, noté « sem. »). */
export function periodLabel(period: string, granularity: Granularity): string {
  const [y, m, d] = period.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d || 1));
  if (granularity === "month") {
    return new Intl.DateTimeFormat("fr-FR", { month: "short", year: "numeric", timeZone: "UTC" }).format(date);
  }
  const day = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", timeZone: "UTC" }).format(date);
  return granularity === "week" ? `sem. du ${day}` : day;
}

interface Datum extends Period {
  label: string;
  value: number;
}

function PeriodTooltip({ active, payload }: { active?: boolean; payload?: { payload: Datum }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-medium">{p.label}</p>
      <p>
        Résultat : <RValue value={p.total_r} className="font-semibold" />
      </p>
      <p className="text-muted-foreground">
        {p.trades} trade{p.trades > 1 ? "s" : ""} · {p.wins} G / {p.losses} P / {p.break_even} BE
      </p>
      <p className="text-muted-foreground">Win rate : {p.win_rate === null ? "non défini" : formatPercent(p.win_rate)}</p>
    </div>
  );
}

/**
 * Résultat en R par période. Barres divergentes autour de zéro : le sens de la barre (haut/bas) porte la
 * polarité, la couleur la renforce. Barres ≤ 24 px, extrémité arrondie côté donnée, base droite.
 */
export function PeriodChart({
  periods,
  granularity,
  onGranularityChange,
}: {
  periods: Period[];
  granularity: Granularity;
  onGranularityChange: (g: Granularity) => void;
}) {
  const data: Datum[] = periods.map((p) => ({ ...p, label: periodLabel(p.period, granularity), value: Number(p.total_r ?? 0) }));

  return (
    <figure>
      <div role="group" aria-label="Granularité" className="mb-3 flex gap-2">
        {(Object.keys(GRANULARITY_LABEL) as Granularity[]).map((g) => (
          <Button
            key={g}
            size="sm"
            variant={g === granularity ? "default" : "outline"}
            aria-pressed={g === granularity}
            onClick={() => onGranularityChange(g)}
          >
            {GRANULARITY_LABEL[g]}
          </Button>
        ))}
      </div>

      <div role="img" aria-label={`Résultat en R par ${GRANULARITY_LABEL[granularity].toLowerCase()}, ${periods.length} périodes`}>
        <ResponsiveContainer width="100%" height={260} initialDimension={{ width: 640, height: 260 }}>
          <BarChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid vertical={false} stroke={CHART.grid} strokeWidth={1} />
            <XAxis dataKey="label" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: CHART.grid }} minTickGap={16} />
            <YAxis
              width={44}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              domain={[(min: number) => Math.min(0, min), (max: number) => Math.max(0, max)]}
              tickFormatter={(v: number) => `${v} R`}
            />
            <ReferenceLine y={0} stroke={CHART.axis} strokeOpacity={0.5} />
            <Tooltip content={<PeriodTooltip />} cursor={{ fill: "rgb(255 255 255 / 6%)" }} />
            <Bar dataKey="value" maxBarSize={24} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.period} fill={d.value >= 0 ? CHART.positive : CHART.negative} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Voir les données</summary>
        <div className="mt-2 max-h-64 overflow-auto rounded-lg border border-border">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Résultat par {GRANULARITY_LABEL[granularity].toLowerCase()}</caption>
            <thead className="sticky top-0 bg-card text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2">Période</th>
                <th scope="col" className="px-3 py-2 text-right">Trades</th>
                <th scope="col" className="px-3 py-2 text-right">G / P / BE</th>
                <th scope="col" className="px-3 py-2 text-right">Win rate</th>
                <th scope="col" className="px-3 py-2 text-right">Résultat</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.period} className="border-t border-border">
                  <td className="px-3 py-1.5">{p.label}</td>
                  <td className="tabular px-3 py-1.5 text-right">{p.trades}</td>
                  <td className="tabular px-3 py-1.5 text-right">
                    {p.wins} / {p.losses} / {p.break_even}
                  </td>
                  <td className="tabular px-3 py-1.5 text-right">{p.win_rate === null ? "Non défini" : formatPercent(p.win_rate)}</td>
                  <td className="px-3 py-1.5 text-right"><RValue value={p.total_r} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
