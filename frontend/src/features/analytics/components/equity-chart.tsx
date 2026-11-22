"use client";

import { Area, AreaChart, CartesianGrid, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { RValue } from "@/components/shared/r-value";
import { useTimeZone } from "@/features/auth/auth-provider";
import { formatDateTime } from "@/lib/datetime";
import { formatR } from "@/lib/format";
import type { EquityPoint } from "@/types/api";
import { AXIS_TICK, CHART } from "../chart-theme";

interface Datum extends EquityPoint {
  value: number; // uniquement pour la géométrie du graphique ; les valeurs affichées restent les chaînes exactes du serveur
}

function PointTooltip({ active, payload }: { active?: boolean; payload?: { payload: Datum }[] }) {
  const tz = useTimeZone();
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-medium">
        #{point.index} · {point.name}
      </p>
      <p className="text-muted-foreground">
        {point.asset} · clôturé le {formatDateTime(point.closed_at, tz)}
      </p>
      <p className="mt-1">
        Résultat : <RValue value={point.realized_rr} className="font-medium" />
      </p>
      <p>
        Cumul : <RValue value={point.cumulative_r} className="font-semibold" />
      </p>
    </div>
  );
}

/** Courbe de performance cumulée (R). Série unique : ligne 2 px + aire à ~10 %, sans légende. */
export function EquityChart({ points, totalR }: { points: EquityPoint[]; totalR: string | null }) {
  const tz = useTimeZone();
  const data: Datum[] = points.map((p) => ({ ...p, value: Number(p.cumulative_r) }));
  const last = data.at(-1);

  return (
    <figure>
      <div role="img" aria-label={`Courbe de performance cumulée sur ${points.length} trades, total ${formatR(totalR, { signed: true })}`}>
        <ResponsiveContainer width="100%" height={280} initialDimension={{ width: 640, height: 280 }}>
          <AreaChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid vertical={false} stroke={CHART.grid} strokeWidth={1} />
            <XAxis
              dataKey="index"
              type="number"
              domain={[1, Math.max(points.length, 2)]}
              allowDecimals={false}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
              tickFormatter={(v: number) => `#${v}`}
              minTickGap={24}
            />
            <YAxis
              width={44}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              domain={[(min: number) => Math.min(0, min), (max: number) => Math.max(0, max)]}
              tickFormatter={(v: number) => `${v} R`}
            />
            <ReferenceLine y={0} stroke={CHART.axis} strokeOpacity={0.5} />
            <Tooltip content={<PointTooltip />} cursor={{ stroke: CHART.axis, strokeWidth: 1 }} />
            <Area
              type="linear" /* segments droits : un lissage suggérerait des valeurs entre deux trades qui n'existent pas */
              dataKey="value"
              stroke={CHART.line}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              fill={CHART.line}
              fillOpacity={0.1}
              dot={false}
              activeDot={{ r: 4, fill: CHART.line, stroke: CHART.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
            {last && <ReferenceDot x={last.index} y={last.value} r={4} fill={CHART.line} stroke={CHART.surface} strokeWidth={2} />}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Voir les données</summary>
        <div className="mt-2 max-h-64 overflow-auto rounded-lg border border-border">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Performance cumulée trade par trade</caption>
            <thead className="sticky top-0 bg-card text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2">#</th>
                <th scope="col" className="px-3 py-2">Clôturé le</th>
                <th scope="col" className="px-3 py-2">Trade</th>
                <th scope="col" className="px-3 py-2 text-right">Résultat</th>
                <th scope="col" className="px-3 py-2 text-right">Cumul</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.trade_id} className="border-t border-border">
                  <td className="tabular px-3 py-1.5">{p.index}</td>
                  <td className="px-3 py-1.5 whitespace-nowrap">{formatDateTime(p.closed_at, tz)}</td>
                  <td className="px-3 py-1.5">
                    {p.name} <span className="text-muted-foreground">· {p.asset}</span>
                  </td>
                  <td className="px-3 py-1.5 text-right"><RValue value={p.realized_rr} /></td>
                  <td className="px-3 py-1.5 text-right"><RValue value={p.cumulative_r} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
