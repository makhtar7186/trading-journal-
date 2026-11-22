"use client";

import { useEffect, useState } from "react";
import { ChevronDown, SlidersHorizontal, X } from "lucide-react";

import { FilterSelect } from "@/components/shared/filter-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useStrategies } from "@/features/strategies/hooks";
import { DIRECTION_OPTIONS, MARKET_OPTIONS, STATUS_OPTIONS } from "@/lib/labels";

export interface TradeFilterValues {
  search: string;
  status: string;
  market_type: string;
  direction: string;
  strategy: string;
  date_from: string;
  date_to: string;
  ordering: string;
}

export const ORDERING_OPTIONS: [string, string][] = [
  ["-trade_date", "Date (récent d'abord)"],
  ["trade_date", "Date (ancien d'abord)"],
  ["-realized_rr", "RR réalisé (meilleur)"],
  ["realized_rr", "RR réalisé (pire)"],
  ["asset", "Actif (A→Z)"],
];

export function TradeFilters({
  values,
  onChange,
  onReset,
  hasActiveFilters,
}: {
  values: TradeFilterValues;
  onChange: (patch: Partial<TradeFilterValues>) => void;
  onReset: () => void;
  hasActiveFilters: boolean;
}) {
  const strategies = useStrategies();

  // La recherche est temporisée pour ne pas interroger l'API à chaque frappe.
  // `draft` = saisie en attente ; tant qu'elle diffère de l'URL, c'est elle qui est affichée.
  const [draft, setDraft] = useState<string | null>(null);
  const search = draft !== null && draft !== values.search ? draft : values.search;
  useEffect(() => {
    if (draft === null || draft === values.search) return;
    const timer = setTimeout(() => onChange({ search: draft }), 350);
    return () => clearTimeout(timer);
  }, [draft, values.search, onChange]);

  const [open, setOpen] = useState(false);

  return (
    <div className="mb-4 rounded-xl border border-border bg-card p-4">
      {/* Mobile : les filtres sont repliés pour laisser la place aux résultats */}
      <Button
        variant="ghost"
        className="w-full justify-between md:hidden"
        aria-expanded={open}
        aria-controls="trade-filters-panel"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="flex items-center gap-2">
          <SlidersHorizontal aria-hidden /> Filtres
          {hasActiveFilters && (
            <span className="rounded-full bg-primary px-2 text-xs text-primary-foreground">actifs</span>
          )}
        </span>
        <ChevronDown aria-hidden className={open ? "rotate-180" : ""} />
      </Button>
      <div
        id="trade-filters-panel"
        className={`grid gap-3 sm:grid-cols-2 lg:grid-cols-4 ${open ? "mt-3 grid" : "hidden md:grid"}`}
      >
        <div className="sm:col-span-2">
          <Label htmlFor="f-search" className="text-xs text-muted-foreground">
            Recherche (nom ou actif)
          </Label>
          <Input
            id="f-search"
            type="search"
            className="mt-1"
            placeholder="ex. EURUSD, breakout…"
            value={search}
            onChange={(e) => setDraft(e.target.value)}
          />
        </div>
        <FilterSelect
          id="f-status"
          label="Statut"
          value={values.status}
          onChange={(v) => onChange({ status: v })}
          options={STATUS_OPTIONS}
          allLabel="Tous les statuts"
        />
        <FilterSelect
          id="f-market"
          label="Marché"
          value={values.market_type}
          onChange={(v) => onChange({ market_type: v })}
          options={MARKET_OPTIONS}
          allLabel="Tous les marchés"
        />
        <FilterSelect
          id="f-direction"
          label="Sens"
          value={values.direction}
          onChange={(v) => onChange({ direction: v })}
          options={DIRECTION_OPTIONS}
          allLabel="Achat et vente"
        />
        <FilterSelect
          id="f-strategy"
          label="Stratégie"
          value={values.strategy}
          onChange={(v) => onChange({ strategy: v })}
          options={(strategies.data?.results ?? []).map((s) => [s.id, s.name])}
          allLabel="Toutes les stratégies"
        />
        <div>
          <Label htmlFor="f-from" className="text-xs text-muted-foreground">
            Du
          </Label>
          <Input
            id="f-from"
            type="date"
            className="mt-1"
            value={values.date_from}
            max={values.date_to || undefined}
            onChange={(e) => onChange({ date_from: e.target.value })}
          />
        </div>
        <div>
          <Label htmlFor="f-to" className="text-xs text-muted-foreground">
            Au
          </Label>
          <Input
            id="f-to"
            type="date"
            className="mt-1"
            value={values.date_to}
            min={values.date_from || undefined}
            onChange={(e) => onChange({ date_to: e.target.value })}
          />
        </div>
        <div className="sm:col-span-2 lg:col-span-2">
          <FilterSelect
            id="f-ordering"
            label="Tri"
            value={values.ordering}
            onChange={(v) => onChange({ ordering: v || "-trade_date" })}
            options={ORDERING_OPTIONS}
          />
        </div>
        <div className="flex items-end">
          <Button
            variant="ghost"
            onClick={() => {
              setDraft(null);
              onReset();
            }}
            disabled={!hasActiveFilters}
          >
            <X aria-hidden /> Réinitialiser
          </Button>
        </div>
      </div>
    </div>
  );
}
