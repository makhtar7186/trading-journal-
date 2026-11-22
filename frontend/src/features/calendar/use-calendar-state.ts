"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useTimeZone } from "@/features/auth/auth-provider";
import { currentMonth, isValidMonth } from "@/lib/calendar";
import { todayIn } from "@/lib/datetime";

export interface CalendarState {
  month: string;
  /** Jour sélectionné (YYYY-MM-DD) appartenant au mois affiché, ou null. */
  day: string | null;
  market_type: string;
  strategy: string;
}

/** Mois, jour sélectionné et filtres vivent dans l'URL (lien partageable, retour arrière fiable). */
export function useCalendarState() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tz = useTimeZone();
  const today = todayIn(tz);

  const state: CalendarState = useMemo(() => {
    const rawMonth = searchParams.get("month");
    const month = isValidMonth(rawMonth) ? rawMonth : currentMonth(tz);
    const rawDay = searchParams.get("day");
    const day = rawDay && /^\d{4}-\d{2}-\d{2}$/.test(rawDay) && rawDay.startsWith(month) ? rawDay : null;
    return { month, day, market_type: searchParams.get("market_type") ?? "", strategy: searchParams.get("strategy") ?? "" };
  }, [searchParams, tz]);

  const update = useCallback(
    (patch: Partial<CalendarState>) => {
      const next = { ...state, ...patch };
      const params = new URLSearchParams();
      // Le mois courant est la valeur par défaut : on ne l'écrit pas dans l'URL.
      if (next.month !== currentMonth(tz)) params.set("month", next.month);
      if (next.day && next.day.startsWith(next.month)) params.set("day", next.day);
      if (next.market_type) params.set("market_type", next.market_type);
      if (next.strategy) params.set("strategy", next.strategy);
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [state, router, pathname, tz],
  );

  return { state, today, update, filtersActive: !!(state.market_type || state.strategy) };
}
