import { apiFetch, type Query } from "@/services/api-client";
import type { EquityCurve, Granularity, Group, Overview, Performance, Period } from "@/types/api";

/** Filtres acceptés par tous les endpoints (dates = date de clôture, jours dans le fuseau de l'utilisateur). */
export interface AnalyticsParams extends Query {
  date_from?: string;
  date_to?: string;
  market_type?: string;
  asset?: string;
  strategy?: string;
}

export const getOverview = (p: AnalyticsParams) => apiFetch<Overview>("/analytics/overview/", { query: p });
export const getPerformance = (p: AnalyticsParams) => apiFetch<Performance>("/analytics/performance/", { query: p });
export const getEquityCurve = (p: AnalyticsParams) => apiFetch<EquityCurve>("/analytics/equity-curve/", { query: p });

export type GroupDimension = "asset" | "market" | "strategy";
export const getGroups = (dimension: GroupDimension, p: AnalyticsParams) =>
  apiFetch<{ groups: Group[] }>(`/analytics/by-${dimension}/`, { query: p });

export const getPeriods = (granularity: Granularity, p: AnalyticsParams) =>
  apiFetch<{ granularity: Granularity; periods: Period[] }>("/analytics/by-period/", {
    query: { ...p, granularity },
  });
