import { apiFetch } from "@/services/api-client";
import type { CalendarMonth } from "@/types/api";

export interface CalendarParams {
  month: string;
  market_type?: string;
  strategy?: string;
}

/** Un trade clôturé figure à sa date de clôture, un trade ouvert à sa date de prise (jours dans le fuseau de l'utilisateur). */
export const getCalendar = (params: CalendarParams) =>
  apiFetch<CalendarMonth>("/analytics/calendar/", { query: { ...params } });
