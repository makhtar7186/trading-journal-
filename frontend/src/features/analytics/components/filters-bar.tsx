"use client";

import { useState } from "react";
import { ChevronDown, SlidersHorizontal, X } from "lucide-react";

import { FilterSelect } from "@/components/shared/filter-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useStrategies } from "@/features/strategies/hooks";
import { MARKET_OPTIONS } from "@/lib/labels";
import { useGroups } from "../hooks";
import { RANGE_LABEL, RANGE_ORDER, type FilterState, type RangePreset } from "../filters";

/** Période + marché + actif + stratégie. Les dates filtrent la date de CLÔTURE des trades. */
export function FiltersBar({
  state,
  onChange,
  onReset,
  active,
}: {
  state: FilterState;
  onChange: (patch: Partial<FilterState>) => void;
  onReset: () => void;
  active: boolean;
}) {
  const strategies = useStrategies();
  // Actifs proposés : ceux qui ont des trades clôturés (requête sans filtre, mise en cache).
  const assets = useGroups("asset", {});
  const [open, setOpen] = useState(false);

  const strategyOptions: [string, string][] = [
    ["none", "Sans stratégie"],
    ...(strategies.data?.results ?? []).map((s): [string, string] => [s.id, s.name]),
  ];
  const assetOptions: [string, string][] = (assets.data?.groups ?? []).map((g) => [g.key ?? "", g.label]);
  // Conserve l'actif de l'URL même s'il n'a (plus) de trade clôturé.
  if (state.asset && !assetOptions.some(([v]) => v === state.asset)) assetOptions.push([state.asset, state.asset]);

  return (
    <div className="mb-6 rounded-xl border border-border bg-card p-4">
      <div role="radiogroup" aria-label="Période (date de clôture)" className="flex flex-wrap gap-2">
        {RANGE_ORDER.map((range: RangePreset) => (
          <Button
            key={range}
            role="radio"
            aria-checked={state.range === range}
            size="sm"
            variant={state.range === range ? "default" : "outline"}
            onClick={() => onChange({ range })}
          >
            {RANGE_LABEL[range]}
          </Button>
        ))}
      </div>

      {state.range === "custom" && (
        <div className="mt-3 grid max-w-md grid-cols-2 gap-3">
          <div>
            <Label htmlFor="a-from" className="text-xs text-muted-foreground">Du (clôture)</Label>
            <Input id="a-from" type="date" className="mt-1" value={state.date_from} max={state.date_to || undefined} onChange={(e) => onChange({ date_from: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="a-to" className="text-xs text-muted-foreground">Au (inclus)</Label>
            <Input id="a-to" type="date" className="mt-1" value={state.date_to} min={state.date_from || undefined} onChange={(e) => onChange({ date_to: e.target.value })} />
          </div>
        </div>
      )}

      <Button
        variant="ghost"
        className="mt-2 w-full justify-between md:hidden"
        aria-expanded={open}
        aria-controls="analytics-filters-panel"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="flex items-center gap-2">
          <SlidersHorizontal aria-hidden /> Marché, actif, stratégie
        </span>
        <ChevronDown aria-hidden className={open ? "rotate-180" : ""} />
      </Button>
      <div
        id="analytics-filters-panel"
        className={`grid gap-3 sm:grid-cols-2 lg:grid-cols-4 ${open ? "mt-3 grid" : "mt-3 hidden md:grid"}`}
      >
        <FilterSelect id="a-market" label="Marché" value={state.market_type} onChange={(v) => onChange({ market_type: v })} options={MARKET_OPTIONS} allLabel="Tous les marchés" />
        <FilterSelect id="a-asset" label="Actif" value={state.asset} onChange={(v) => onChange({ asset: v })} options={assetOptions} allLabel="Tous les actifs" />
        <FilterSelect id="a-strategy" label="Stratégie" value={state.strategy} onChange={(v) => onChange({ strategy: v })} options={strategyOptions} allLabel="Toutes les stratégies" />
        <div className="flex items-end">
          <Button variant="ghost" onClick={onReset} disabled={!active}>
            <X aria-hidden /> Réinitialiser
          </Button>
        </div>
      </div>
    </div>
  );
}
