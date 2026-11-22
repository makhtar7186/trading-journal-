"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import type { Granularity } from "@/types/api";
import {
  getEquityCurve,
  getGroups,
  getOverview,
  getPerformance,
  getPeriods,
  type AnalyticsParams,
  type GroupDimension,
} from "./api";

export const analyticsKey = ["analytics"] as const;

// keepPreviousData : changer un filtre ne vide pas les graphiques le temps du rechargement.
export const useOverview = (p: AnalyticsParams) =>
  useQuery({ queryKey: [...analyticsKey, "overview", p], queryFn: () => getOverview(p), placeholderData: keepPreviousData });

export const usePerformance = (p: AnalyticsParams) =>
  useQuery({ queryKey: [...analyticsKey, "performance", p], queryFn: () => getPerformance(p), placeholderData: keepPreviousData });

export const useEquityCurve = (p: AnalyticsParams) =>
  useQuery({ queryKey: [...analyticsKey, "equity", p], queryFn: () => getEquityCurve(p), placeholderData: keepPreviousData });

export const useGroups = (dimension: GroupDimension, p: AnalyticsParams) =>
  useQuery({
    queryKey: [...analyticsKey, "groups", dimension, p],
    queryFn: () => getGroups(dimension, p),
    placeholderData: keepPreviousData,
  });

export const usePeriods = (granularity: Granularity, p: AnalyticsParams) =>
  useQuery({
    queryKey: [...analyticsKey, "periods", granularity, p],
    queryFn: () => getPeriods(granularity, p),
    placeholderData: keepPreviousData,
  });
