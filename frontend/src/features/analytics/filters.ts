import { shiftDate, startOfYear, todayIn } from "@/lib/datetime";
import type { AnalyticsParams } from "./api";

export type RangePreset = "7d" | "30d" | "90d" | "ytd" | "all" | "custom";

export const RANGE_LABEL: Record<RangePreset, string> = {
  "7d": "7 jours",
  "30d": "30 jours",
  "90d": "90 jours",
  ytd: "Cette année",
  all: "Tout",
  custom: "Personnalisée",
};

export const RANGE_ORDER: RangePreset[] = ["7d", "30d", "90d", "ytd", "all", "custom"];

/** État des filtres tel qu'il vit dans l'URL (lien partageable). */
export interface FilterState {
  range: RangePreset;
  date_from: string;
  date_to: string;
  market_type: string;
  asset: string;
  strategy: string;
}

export const DEFAULT_FILTERS: FilterState = {
  range: "all",
  date_from: "",
  date_to: "",
  market_type: "",
  asset: "",
  strategy: "",
};

const isPreset = (value: string | null): value is RangePreset => !!value && value in RANGE_LABEL;

export function parseFilterState(params: URLSearchParams): FilterState {
  const range = params.get("range");
  return {
    range: isPreset(range) ? range : DEFAULT_FILTERS.range,
    date_from: params.get("date_from") ?? "",
    date_to: params.get("date_to") ?? "",
    market_type: params.get("market_type") ?? "",
    asset: params.get("asset") ?? "",
    strategy: params.get("strategy") ?? "",
  };
}

/** Ne garde dans l'URL que ce qui diffère des valeurs par défaut. */
export function serializeFilterState(state: FilterState): string {
  const next = new URLSearchParams();
  if (state.range !== DEFAULT_FILTERS.range) next.set("range", state.range);
  if (state.range === "custom") {
    if (state.date_from) next.set("date_from", state.date_from);
    if (state.date_to) next.set("date_to", state.date_to);
  }
  for (const key of ["market_type", "asset", "strategy"] as const) {
    if (state[key]) next.set(key, state[key]);
  }
  return next.toString();
}

export function hasActiveFilters(state: FilterState): boolean {
  return serializeFilterState(state) !== "";
}

/** Résout la période (relative au jour courant dans le fuseau de l'utilisateur) en paramètres d'API. */
export function toApiParams(state: FilterState, timeZone: string | undefined, now: Date = new Date()): AnalyticsParams {
  const params: AnalyticsParams = {};
  const today = todayIn(timeZone, now);
  switch (state.range) {
    case "7d":
      params.date_from = shiftDate(today, -6);
      params.date_to = today;
      break;
    case "30d":
      params.date_from = shiftDate(today, -29);
      params.date_to = today;
      break;
    case "90d":
      params.date_from = shiftDate(today, -89);
      params.date_to = today;
      break;
    case "ytd":
      params.date_from = startOfYear(today);
      params.date_to = today;
      break;
    case "custom":
      if (state.date_from) params.date_from = state.date_from;
      if (state.date_to) params.date_to = state.date_to;
      break;
    default:
      break; // all : pas de bornes
  }
  if (state.market_type) params.market_type = state.market_type;
  if (state.asset) params.asset = state.asset;
  if (state.strategy) params.strategy = state.strategy;
  return params;
}
