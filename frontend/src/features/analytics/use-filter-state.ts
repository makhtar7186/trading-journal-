"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useTimeZone } from "@/features/auth/auth-provider";
import type { AnalyticsParams } from "./api";
import { DEFAULT_FILTERS, hasActiveFilters, parseFilterState, serializeFilterState, toApiParams, type FilterState } from "./filters";

/** Filtres analytics synchronisés avec l'URL ; `params` est directement utilisable pour les requêtes. */
export function useFilterState() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const timeZone = useTimeZone();

  const state = useMemo(() => parseFilterState(new URLSearchParams(searchParams.toString())), [searchParams]);
  const params: AnalyticsParams = useMemo(() => toApiParams(state, timeZone), [state, timeZone]);

  const update = useCallback(
    (patch: Partial<FilterState>) => {
      const next = { ...state, ...patch };
      const query = serializeFilterState(next);
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [state, router, pathname],
  );

  const reset = useCallback(() => router.replace(pathname, { scroll: false }), [router, pathname]);

  return { state, params, update, reset, active: hasActiveFilters(state), defaults: DEFAULT_FILTERS };
}
